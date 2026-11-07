"""Alertas al celular de Daniel por Telegram.

Dos caminos:

1. **Cola en la base** (`alerta_telegram`): cortes y retiros la llenan desde
   donde ocurran (kiosko, PWA, bot, tarea). El bot de la PC servidor, que ya
   está escuchando, manda lo pendiente en cada vuelta. Los kioskos no
   necesitan el token.
2. **Vigilante**: el bot revisa cada vuelta si ya cerró la tienda sin corte
   y si hubo movimientos fuera de horario. Lógica pura en `Vigilante.revisar`.

Todo lo que encola es defensivo: si la tabla aún no existe (base sin
migrar) no rompe la operación que la llamó.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

logger = logging.getLogger("alertas")

_CENT = Decimal("0.01")
# Un corte del dueño con más de esto de diferencia se marca con ⚠️.
TOLERANCIA_DIFERENCIA = Decimal("50.00")
# Minutos después del cierre para avisar que no hubo corte.
MINUTOS_SIN_CORTE = 10
#: Si a esta hora después del cierre sigue sin corte —con propuesta en pie—,
#: es que tampoco corrió el cierre automático (que va a los 45 min).
MINUTOS_CORTE_FALLIDO = 90
#: Margen antes de abrir y después de cerrar: una clienta que se quedó al
#: cierre no es un 🚨 (auditoría 2026-11-07).
MINUTOS_GRACIA_HORARIO = 20
#: Una revisión del vigilante que lleva tanto fallando se avisa por Telegram.
MINUTOS_REVISION_ROTA = 30

#: Cuánto se espera antes de avisar que una pantalla se apagó. Un kiosko que
#: se reinicia tarda un par de minutos en volver a latir (el margen de
#: «encendido» ya son 2.5), y avisar de eso enseñaría a ignorar los avisos.
MINUTOS_PANTALLA_MUERTA = 10.0

#: A partir de qué hora se avisa del respaldo viejo. Un aviso a las 3 de la
#: mañana se lee a las 9 ya mezclado con lo demás, o no se lee.
HORA_AVISO_RESPALDO = 10
MAX_INTENTOS = 5


def _d(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(_CENT)


def _local(momento: datetime | None) -> datetime:
    if momento is None:
        return datetime.now()
    return momento.astimezone().replace(tzinfo=None) if momento.tzinfo else momento


# ----------------------------------------------------------------- cola
def encolar(session, texto: str, botones: str = "") -> bool:
    """Deja la alerta en la cola. Devuelve False (sin romper) si no se pudo.

    `botones` es el teclado con el que se puede contestar el aviso donde
    llega. Va aquí y no se arma al mandarlo: quien encola es el único que
    sabe qué se puede hacer con ese aviso (2026-10-08)."""
    texto = (texto or "").strip()
    if not texto:
        return False
    try:
        from pos_uniformes.database.models import AlertaTelegram

        session.add(AlertaTelegram(
            texto=texto, botones=(botones or "") or None,
            created_at=datetime.now().astimezone(),
        ))
        session.commit()
        return True
    except Exception as exc:  # noqa: BLE001 — base sin la tabla, sin red, etc.
        logger.warning("No se pudo encolar la alerta: %s", exc)
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False


def pendientes(session) -> list:
    from pos_uniformes.database.models import AlertaTelegram

    stmt = (
        select(AlertaTelegram)
        .where(AlertaTelegram.enviado_at.is_(None), AlertaTelegram.intentos < MAX_INTENTOS)
        .order_by(AlertaTelegram.id)
    )
    return list(session.scalars(stmt).all())


#: A partir de cuánto retraso una alerta dice de cuándo es. Una alerta de
#: «ya cerró la tienda sin corte» que llega a la mañana siguiente, sin fecha,
#: se lee como de ahora.
MINUTOS_PARA_FECHAR = 30


def _es_falla_de_red(exc: BaseException) -> bool:
    """¿Falló la red (o Telegram no contestó), o fue Telegram rechazando ESTE
    mensaje? Lo segundo viene como RuntimeError «Telegram respondió: …» desde
    telegram_service._llamar; todo lo demás es red."""
    return not (isinstance(exc, RuntimeError) and str(exc).startswith("Telegram respondió"))


def _fechada(alerta, ahora: datetime | None = None) -> str:
    """El texto, con «(de ayer 18:10)» delante si lleva rato esperando."""
    ahora = ahora or datetime.now().astimezone()
    creada = alerta.created_at
    if creada is None:
        return alerta.texto
    if creada.tzinfo is None:
        # Sin zona solo pasa en SQLite (tests): `encolar` la escribe en hora
        # local con zona y SQLite se la quita. Postgres la devuelve con zona.
        creada = creada.replace(tzinfo=ahora.tzinfo)
    if ahora - creada < timedelta(minutes=MINUTOS_PARA_FECHAR):
        return alerta.texto
    local = _local(creada)
    cuando = f"de las {local:%H:%M}" if local.date() == _local(ahora).date() else f"de ayer {local:%H:%M}" \
        if local.date() == _local(ahora).date() - timedelta(days=1) else f"del {local:%d/%m %H:%M}"
    return f"🕒 ({cuando}) {alerta.texto}"


def enviar_pendientes(session, enviar, ahora: datetime | None = None) -> int:
    """Manda cada alerta pendiente con `enviar(texto)`; marca enviadas. Devuelve cuántas salieron.

    Los intentos solo se cuentan cuando Telegram rechazó ESE mensaje. Sin red
    no se cuenta nada: antes, en un apagón de internet, cada vuelta del bot
    (25-40 s) sumaba un intento y a los cinco (~3 min) la alerta se descartaba
    para siempre; en una hora sin línea se perdían cortes, retiros y «cierre
    sin corte», y al volver el bot decía «lo que quedó en cola ya te va
    llegando» (2026-10-10)."""
    enviadas = 0
    for alerta in pendientes(session):
        try:
            # Con teclado se llama con dos argumentos; sin él, con uno. Así
            # un enviador de los de antes —que recibe solo el texto— sigue
            # sirviendo para los avisos de siempre, que son casi todos.
            texto = _fechada(alerta, ahora)
            if alerta.botones:
                enviar(texto, alerta.botones)
            else:
                enviar(texto)
        except Exception as exc:  # noqa: BLE001
            if _es_falla_de_red(exc):
                logger.warning("Alerta %s no salió (sin línea, se reintenta): %s", alerta.id, exc)
            else:
                alerta.intentos = int(alerta.intentos or 0) + 1
                logger.warning("Alerta %s rechazada (intento %s): %s", alerta.id, alerta.intentos, exc)
            session.commit()
            break  # sin red: lo demás tampoco va a salir ahora
        alerta.enviado_at = datetime.now().astimezone()
        enviadas += 1
        session.commit()
    return enviadas


# ----------------------------------------------------------------- textos
def texto_alerta_corte(corte, venta_efectivo, *, pagos=None, retiros=None) -> str:
    """Aviso al momento de cualquier corte: quién, venta, pagos, lo que se saca."""
    quien = str(corte.creado_por or "").upper() or "?"
    hora = _local(getattr(corte, "hasta", None) or getattr(corte, "created_at", None)).strftime("%H:%M")
    se_saca = (_d(corte.monto_final) - _d(corte.reactivo_final)).quantize(_CENT)
    lineas = [f"🧾 Corte hecho por {quien} a las {hora}"]
    lineas.append(f"Venta efectivo ${_d(venta_efectivo):,.2f}")
    detalle = []
    if _d(corte.retiros_pagos) > 0:
        detalle.append(f"pagos ${_d(corte.retiros_pagos):,.2f}")
    if _d(corte.otros_retiros) > 0:
        detalle.append(f"retiros ${_d(corte.otros_retiros):,.2f}")
    if detalle:
        lineas[-1] += " · " + " · ".join(detalle)
    for p in pagos or []:
        nombre = (getattr(p, "employee_name", "") or getattr(p, "employee_code", "")).split()[0]
        lineas.append(f"  💵 {nombre}: ${_d(p.total):,.2f}")
    lineas.append(f"Se saca ${se_saca:,.2f} · reactivo queda ${_d(corte.reactivo_final):,.2f}")
    if getattr(corte, "hasta", None) is not None:
        dif = (_d(corte.monto_final) - _d(corte.monto_esperado)).quantize(_CENT)
        if dif != 0 and quien == "VEND-1":
            # Su corte con ajuste: solo el dueño recibe esto; el encargado ve la cifra final.
            lineas.append(f"Ajuste: real ${_d(corte.monto_esperado):,.2f} → oficial ${_d(corte.monto_final):,.2f} ({'+' if dif > 0 else '−'}${abs(dif):,.2f})")
        elif dif != 0:
            marca = "⚠️ " if abs(dif) >= TOLERANCIA_DIFERENCIA else ""
            lineas.append(f"{marca}{'Sobraron' if dif > 0 else 'FALTARON'} ${abs(dif):,.2f}")
    if corte.nota:
        lineas.append(f"Nota: {corte.nota}")
    return "\n".join(lineas)


def texto_alerta_retiro(retiro) -> str:
    hora = _local(getattr(retiro, "created_at", None)).strftime("%H:%M")
    return f"💸 Retiro del cajón: ${_d(retiro.monto):,.2f} — {retiro.motivo} ({str(retiro.creado_por).upper()}, {hora})"


def texto_sin_corte(dia: date, cierre) -> str:
    return (
        f"⏰ Ya cerró la tienda ({cierre.strftime('%H:%M')}) y hoy no se ha hecho corte.\n"
        "Manda /corte para hacerlo ahora."
    )


def texto_fuera_de_horario(row, apertura, cierre) -> str:
    momento = _local(row.created_at)
    nombre = (row.employee_name or row.employee_code or "?").split()[0]
    return (
        f"🚨 Movimiento fuera de horario: {row.tipo} ${_d(row.monto_total):,.2f} por {nombre} "
        f"a las {momento.strftime('%H:%M')} (horario {apertura.strftime('%H:%M')}–{cierre.strftime('%H:%M')})"
    )


# ----------------------------------------------------------------- vigilante
_ARCHIVO_MEMORIA = "bot_vigilante.json"


def ruta_memoria():
    """Dónde recuerda el vigilante qué ya avisó hoy (junto a bot_conexion.json)."""
    from pos_uniformes.utils.config import runtime_base_dir

    return runtime_base_dir() / "data" / _ARCHIVO_MEMORIA


def _cargar_memoria() -> dict:
    """{"dia_respaldo_avisado": date | None, ...}. Vacío si no hay o no se lee."""
    import json

    try:
        ruta = ruta_memoria()
        if not ruta.exists():
            return {}
        crudo = json.loads(ruta.read_text(encoding="utf-8"))
        salida = {}
        for clave in ("dia_respaldo_avisado", "dia_sin_corte_avisado", "dia_corte_fallido_avisado", "dia_pantallas"):
            valor = crudo.get(clave)
            try:
                salida[clave] = date.fromisoformat(valor) if valor else None
            except (TypeError, ValueError):
                salida[clave] = None
        try:
            salida["ultimo_id"] = int(crudo["ultimo_id"]) if crudo.get("ultimo_id") is not None else None
        except (TypeError, ValueError):
            salida["ultimo_id"] = None
        salida["pantallas_avisadas"] = [str(x) for x in (crudo.get("pantallas_avisadas") or [])]
        return salida
    except Exception:  # noqa: BLE001 — sin memoria se avisa una vez más, no se cae
        return {}


def _guardar_memoria(datos: dict) -> None:
    import json

    try:
        ruta = ruta_memoria()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        from pos_uniformes.utils.archivo_atomico import escribir_json

        escribir_json(ruta, {
            k: (v.isoformat() if isinstance(v, date) else v) for k, v in datos.items()
        })
    except Exception:  # noqa: BLE001 — recordar no vale un error
        pass


@dataclass
class Vigilante:
    """Estado entre vueltas del bot: qué ya se avisó y hasta qué movimiento se revisó."""

    ultimo_id: int | None = None
    dia_sin_corte_avisado: date | None = None
    dia_respaldo_avisado: date | None = None
    #: Pantallas que SÍ estuvieron prendidas hoy: {identificador: nombre}.
    pantallas_vistas_hoy: dict = field(default_factory=dict, repr=False)
    #: Desde cuándo se ve apagada cada una (para no avisar de un reinicio).
    pantallas_sin_latir: dict = field(default_factory=dict, repr=False)
    #: De cuáles ya se avisó, para no repetirlo cada 25 segundos.
    pantallas_avisadas: set = field(default_factory=set, repr=False)
    dia_de_las_pantallas: date | None = None
    dia_corte_fallido_avisado: date | None = None
    #: Qué revisión está fallando y desde cuándo (y si ya se avisó).
    _fallando: dict = field(default_factory=dict, repr=False)
    _avisadas_guardadas: tuple = field(default=(None, ()), repr=False)
    _apertura: object = field(default=None, repr=False)

    # Lo «avisado hoy» se guarda en disco. Vivía solo en memoria, y cada vez
    # que el bot se reiniciaba (al actualizar, al abrir el POS, al reiniciar
    # la PC) volvía a mandar el mismo aviso de respaldo: Daniel recibió dos
    # iguales a las 14:42 (2026-10-10). Reiniciar no es un día nuevo.
    def __post_init__(self) -> None:
        memoria = _cargar_memoria()
        if self.dia_respaldo_avisado is None:
            self.dia_respaldo_avisado = memoria.get("dia_respaldo_avisado")
        if self.dia_sin_corte_avisado is None:
            self.dia_sin_corte_avisado = memoria.get("dia_sin_corte_avisado")
        if self.dia_corte_fallido_avisado is None:
            self.dia_corte_fallido_avisado = memoria.get("dia_corte_fallido_avisado")
        # De qué pantallas ya se avisó hoy: vivía solo en memoria y cada
        # reinicio del bot volvía a avisar la misma pantalla apagada, y el
        # «✅ ya volvió» de las de antes nunca llegaba (auditoría 2026-11-07).
        self._avisadas_guardadas = (memoria.get("dia_pantallas"), tuple(memoria.get("pantallas_avisadas") or ()))
        if self.ultimo_id is None:
            # Hasta qué venta se revisó el horario. Sin esto, cada reinicio
            # «marcaba dónde vamos» y las ventas hechas mientras el bot estaba
            # abajo nunca se revisaban (2026-10-10).
            self.ultimo_id = memoria.get("ultimo_id")

    def _recordar(self) -> None:
        _guardar_memoria({
            "dia_respaldo_avisado": self.dia_respaldo_avisado,
            "dia_sin_corte_avisado": self.dia_sin_corte_avisado,
            "dia_corte_fallido_avisado": self.dia_corte_fallido_avisado,
            "ultimo_id": self.ultimo_id,
            "dia_pantallas": self.dia_de_las_pantallas,
            "pantallas_avisadas": sorted(self.pantallas_avisadas),
        })

    def revisar(self, session, ahora: datetime | None = None) -> list[str]:
        """Devuelve los textos a mandar ahora (puede ser vacío).

        Cada revisión va por su lado: antes, si una consulta tronaba, la vuelta
        entera fallaba y con ella las pantallas y los descansos, y el error
        solo quedaba en el log (auditoría 2026-11-07). Ahora la que truene se
        salta, y si lleva media hora fallando se dice por Telegram."""
        ahora = _local(ahora or datetime.now().astimezone())
        textos: list = []
        for nombre, revision in (
            ("los movimientos fuera de horario", lambda: self._movimientos_fuera_de_horario(session, ahora)),
            ("si se hizo el corte", lambda: self._cierre_sin_corte(session, ahora)),
            ("el respaldo", lambda: self._respaldo_viejo(ahora)),
            ("las pantallas", lambda: self._pantalla_apagada(session, ahora)),
        ):
            try:
                textos += revision()
            except Exception as exc:  # noqa: BLE001 — una revisión rota no apaga a las demás
                try:
                    session.rollback()
                except Exception:  # noqa: BLE001
                    pass
                textos += self._revision_fallo(nombre, exc, ahora)
            else:
                self._fallando.pop(nombre, None)
        return textos

    def _revision_fallo(self, nombre: str, exc: BaseException, ahora: datetime) -> list[str]:
        logger.warning("Vigilante: no pude revisar %s", nombre, exc_info=True)
        desde, avisado = self._fallando.get(nombre, (ahora, False))
        self._fallando[nombre] = (desde, avisado)
        if avisado or (ahora - desde) < timedelta(minutes=MINUTOS_REVISION_ROTA):
            return []
        self._fallando[nombre] = (desde, True)
        return [f"⚠️ Desde las {desde:%H:%M} no puedo revisar {nombre}: {str(exc)[:150]}\n"
                "Mientras tanto, de eso no te va a llegar ningún aviso."]

    def _movimientos_fuera_de_horario(self, session, ahora: datetime) -> list[str]:
        from pos_uniformes.database.models import LibretaVenta
        from pos_uniformes.services.horario_tienda_service import hora_apertura, hora_cierre

        if self.ultimo_id is None:
            # Primera vuelta de la vida del bot (sin memoria): no reclamar lo
            # viejo, solo marcar dónde vamos.
            self.ultimo_id = int(session.scalar(select(func.coalesce(func.max(LibretaVenta.id), 0))) or 0)
            self._recordar()
            return []
        rows = list(session.scalars(
            select(LibretaVenta).where(LibretaVenta.id > self.ultimo_id).order_by(LibretaVenta.id)
        ).all())
        fuera = []
        gracia = timedelta(minutes=MINUTOS_GRACIA_HORARIO)
        for row in rows:
            self.ultimo_id = max(self.ultimo_id, int(row.id))
            momento = _local(row.created_at)
            apertura, cierre = hora_apertura(momento.date()), hora_cierre(momento.date())
            # Con margen: una venta a las 18:03 de una clienta que se quedó al
            # cierre no es noticia (auditoría 2026-11-07).
            abre = (datetime.combine(momento.date(), apertura) - gracia).time()
            cierra = (datetime.combine(momento.date(), cierre) + gracia).time()
            if not (abre <= momento.time() <= cierra):
                fuera.append((row, apertura, cierre))
        if rows:
            self._recordar()
        if len(fuera) <= 1:
            return [texto_fuera_de_horario(*f) for f in fuera]
        # Varias en la misma vuelta (Daniel capturando de noche): un mensaje,
        # no una ráfaga.
        _, apertura, cierre = fuera[0]
        renglones = [f"🚨 {len(fuera)} movimientos fuera de horario (horario {apertura:%H:%M}–{cierre:%H:%M}):"]
        for row, _a, _c in fuera[:10]:
            nombre = (row.employee_name or row.employee_code or "?").split()[0]
            renglones.append(f"• {_local(row.created_at):%H:%M} {row.tipo} ${_d(row.monto_total):,.2f} por {nombre}")
        if len(fuera) > 10:
            renglones.append(f"• … y {len(fuera) - 10} más")
        return ["\n".join(renglones)]

    def _cierre_sin_corte(self, session, ahora: datetime) -> list[str]:
        from pos_uniformes.database.models import LibretaCorte, LibretaVenta
        from pos_uniformes.services.horario_tienda_service import hora_cierre

        hoy = ahora.date()
        if self.dia_sin_corte_avisado == hoy:
            return self._corte_que_no_se_hizo(session, ahora)
        cierre = hora_cierre(hoy)
        if ahora < datetime.combine(hoy, cierre) + timedelta(minutes=MINUTOS_SIN_CORTE):
            return []
        inicio = datetime.combine(hoy, datetime.min.time()).astimezone()
        hubo_corte = session.scalar(
            select(func.count(LibretaCorte.id)).where(LibretaCorte.fecha == hoy)
        )
        self.dia_sin_corte_avisado = hoy  # se avisa una sola vez al día (o se anota que no hacía falta)
        self._recordar()
        if hubo_corte:
            return []
        # Si hoy hubo propuesta de corte, esa conversación ya está en marcha:
        # o dijo /nocorte (y este aviso lo contradiría) o el cierre automático
        # lo hace solo a los 45 min. Cuatro mensajes por una decisión era
        # demasiado (2026-10-10). Este aviso queda para cuando la tarea de la
        # propuesta no corrió.
        try:
            from pos_uniformes.services import corte_propuesta_service as prop

            p = prop.leer()
            if p.hay and p.fecha == hoy:
                return []
        except Exception:  # noqa: BLE001 — sin propuesta legible, se avisa como siempre
            pass
        hubo_movimiento = session.scalar(
            select(func.count(LibretaVenta.id)).where(LibretaVenta.created_at >= inicio)
        )
        if not hubo_movimiento:
            return []
        return [texto_sin_corte(hoy, cierre)]


    def _corte_que_no_se_hizo(self, session, ahora: datetime) -> list[str]:
        """Segunda mirada, a la hora y media del cierre.

        A los 10 min el vigilante ve la propuesta en pie y se calla: la
        conversación está en marcha y el cierre automático va a los 45. Pero
        si ese cierre truena o la tarea no corre, el error se queda en una
        consola oculta y el día sin corte, sin que nadie se entere
        (auditoría 2026-11-07)."""
        from pos_uniformes.database.models import LibretaCorte, LibretaVenta
        from pos_uniformes.services.horario_tienda_service import hora_cierre

        hoy = ahora.date()
        if self.dia_corte_fallido_avisado == hoy:
            return []
        if ahora < datetime.combine(hoy, hora_cierre(hoy)) + timedelta(minutes=MINUTOS_CORTE_FALLIDO):
            return []
        from pos_uniformes.services import corte_propuesta_service as prop

        p = prop.leer()
        self.dia_corte_fallido_avisado = hoy
        self._recordar()
        if not (p.hay and p.fecha == hoy) or p.cancelado:
            return []   # sin propuesta ya avisó _cierre_sin_corte; «Hoy no» es una decisión
        if session.scalar(select(func.count(LibretaCorte.id)).where(LibretaCorte.fecha == hoy)):
            return []
        inicio = datetime.combine(hoy, datetime.min.time()).astimezone()
        if not session.scalar(select(func.count(LibretaVenta.id)).where(LibretaVenta.created_at >= inicio)):
            return []
        return [
            "⚠️ El corte de hoy no se hizo: ni con la propuesta ni con el cierre automático.\n"
            "Lo vendido sigue esperando corte. Hazlo con /corte cuando puedas."
        ]

    def _respaldo_viejo(self, ahora: datetime) -> list[str]:
        """Avisa una vez al día si el último respaldo ya tiene días.

        Esta vigilancia vive aquí, en el bot, y no en la tarea del respaldo, a
        propósito: la tarea solo puede avisar de lo que le pasa mientras corre.
        Si se borra, si la PC pasó días apagada, o si nunca se instaló, no falla
        nada y por lo tanto no avisa nada — el silencio se ve igual que el
        éxito. El bot lo nota desde fuera.
        """
        hoy = ahora.date()
        if self.dia_respaldo_avisado == hoy:
            return []
        # Después de abrir: un aviso a las 3 de la mañana no lo lee nadie.
        if ahora.hour < HORA_AVISO_RESPALDO:
            return []
        try:
            from pos_uniformes.services import respaldo_estado_service as est

            estado = est.leer_estado()
        except Exception as exc:  # noqa: BLE001 — el vigilante nunca puede tumbar al bot
            # Antes se marcaba «avisado» ANTES de leer: si leer tronaba, ese
            # día no salía nada y se daba por avisado. El silencio no es éxito.
            self.dia_respaldo_avisado = hoy
            self._recordar()
            logger.warning("No se pudo revisar el respaldo", exc_info=True)
            return [f"⚠️ No pude revisar el respaldo: {exc}"]
        self.dia_respaldo_avisado = hoy
        self._recordar()
        if estado.al_dia:
            return []
        try:
            from pos_uniformes.services import telegram_respaldo_service as rs

            return [(est.texto_sin_respaldo(estado), rs.botones_del_aviso())]
        except Exception:  # noqa: BLE001 — sin botón, el aviso sale igual
            return [est.texto_sin_respaldo(estado)]


    def _pantalla_apagada(self, session, ahora: datetime) -> list[str]:
        """Avisa cuando una pantalla que estaba trabajando se apaga.

        Daniel lo pidió el 2026-10-08: hasta hoy, una pantalla muerta solo se
        sabía preguntando `/pulso`. Y una pantalla muerta en horas de tienda
        es una muchacha que no puede cotizar ni vender — de lo más caro que
        puede pasar sin que nadie se entere.

        Se avisa de la que **estaba prendida hoy y se apagó**, no de la que no
        está prendida. No es lo mismo: la lista incluye la Mac de Daniel, que
        casi nunca está, y un kiosko descompuesto desde hace una semana, que
        ya se sabe. Lo que es noticia es el cambio.

        Y se espera un rato antes de decir nada: un kiosko que se reinicia
        tarda un par de minutos en volver a latir, y avisar de eso sería
        enseñar a ignorar los avisos.
        """
        from pos_uniformes.services.horario_tienda_service import hora_apertura, hora_cierre

        # Todo lo de aquí se compara contra el último latido, que viene de la
        # base: se trabaja sin zona para que las dos horas sean comparables.
        ahora = _local(ahora)
        hoy = ahora.date()
        dia_nuevo = self.dia_de_las_pantallas != hoy

        hora = ahora.time()
        if not (hora_apertura(hoy) <= hora <= hora_cierre(hoy)):
            return []

        try:
            from pos_uniformes.services import satelite_registry_service as rsvc

            # Con zona: `ultimo_visto` viene de Postgres con zona, y restarle
            # una hora sin zona levanta TypeError. Ese TypeError caía aquí
            # abajo, en el except, y este aviso devolvió [] en silencio desde
            # que existe (se vio el 2026-10-10).
            estado = rsvc.listar_con_estado(session, ahora=ahora.astimezone())
        except Exception:  # noqa: BLE001 — el vigilante nunca tumba al bot
            logger.warning("No se pudo revisar las pantallas", exc_info=True)
            return []

        if dia_nuevo:
            # Día nuevo: lo de ayer no se arrastra. Un kiosko apagado anoche
            # no es noticia hoy en la mañana. Se limpia AQUÍ, ya con la base
            # contestando: si la primera lectura del día fallaba, el día
            # quedaba marcado y la siembra de abajo ya no se repetía
            # (2026-10-10).
            self.dia_de_las_pantallas = hoy
            self.pantallas_vistas_hoy = {}
            self.pantallas_sin_latir = {}
            self.pantallas_avisadas = set()
            dia_guardado, guardadas = self._avisadas_guardadas
            if dia_guardado == hoy:
                self.pantallas_avisadas = set(guardadas)
            # Quién trabajó hoy sale del DATO y no solo de lo que este
            # vigilante alcanzó a ver. Si no, un reinicio del bot a media
            # mañana le borraba la memoria y una pantalla muerta desde antes
            # ya no se reportaba nunca.
            for s in estado:
                visto = s.get("ultimo_visto")
                if visto is not None and _local(visto).date() == hoy:
                    self.pantallas_vistas_hoy[s["identificador"]] = s["nombre"]

        textos: list[str] = []
        for s in estado:
            ident, nombre = s["identificador"], s["nombre"]
            if s["online"]:
                self.pantallas_vistas_hoy[ident] = nombre
                self.pantallas_sin_latir.pop(ident, None)
                if ident in self.pantallas_avisadas:
                    # Volvió: cerrar el aviso vale tanto como darlo. Sin esto,
                    # queda con la duda de si tiene que ir a la tienda.
                    self.pantallas_avisadas.discard(ident)
                    self._avisadas_guardadas = (hoy, tuple(self.pantallas_avisadas))
                    self._recordar()
                    textos.append(f"✅ {nombre} ya volvió.")
                continue
            if ident not in self.pantallas_vistas_hoy:
                continue          # no es que se apagara: nunca estuvo hoy
            if ident in self.pantallas_avisadas:
                continue
            # Desde el ÚLTIMO LATIDO, no desde que el bot lo notó: si el bot
            # se reinicia, lo contrario volvería a esperar diez minutos con la
            # pantalla muerta desde hace media hora.
            visto = s.get("ultimo_visto")
            desde = _local(visto) if visto is not None else None
            if desde is None:
                desde = self.pantallas_sin_latir.setdefault(ident, ahora)
            minutos = (ahora - desde).total_seconds() / 60.0
            if minutos < MINUTOS_PANTALLA_MUERTA:
                continue
            self.pantallas_avisadas.add(ident)
            self._avisadas_guardadas = (hoy, tuple(self.pantallas_avisadas))
            self._recordar()
            textos.append(
                f"⚠️ {nombre} lleva {int(minutos)} min sin responder, y la tienda "
                "está abierta.\nSi está apagada, ahí no se puede cotizar ni vender."
            )
        return textos


_DIAS_QUE_SE_GUARDAN_LAS_ENVIADAS = 30
_ultima_limpieza: date | None = None


def limpiar_viejas(session, hoy: date | None = None) -> int:
    """Borra las alertas enviadas hace más de 30 días. Nadie las limpiaba y
    la tabla crecía sin que nada la mirara (2026-10-10). Las que agotaron
    intentos sin salir se quedan, que son las que vale la pena ver."""
    from sqlalchemy import delete

    from pos_uniformes.database.models import AlertaTelegram

    limite = datetime.now().astimezone() - timedelta(days=_DIAS_QUE_SE_GUARDAN_LAS_ENVIADAS)
    borradas = session.execute(
        delete(AlertaTelegram).where(AlertaTelegram.enviado_at.is_not(None), AlertaTelegram.enviado_at < limite)
    ).rowcount or 0
    session.commit()
    return int(borradas)


def procesar(session_factory, enviar, vigilante: Vigilante | None = None) -> int:
    """Una vuelta completa: manda la cola y lo que vea el vigilante. Nunca truena."""
    global _ultima_limpieza
    enviadas = 0
    try:
        with session_factory() as session:
            if _ultima_limpieza != date.today():
                _ultima_limpieza = date.today()
                limpiar_viejas(session)
            enviadas += enviar_pendientes(session, enviar)
            if vigilante is not None:
                for aviso in vigilante.revisar(session):
                    # El vigilante puede devolver un texto pelón o (texto,
                    # botones): casi ninguno tiene nada que ofrecer.
                    texto, botones = aviso if isinstance(aviso, tuple) else (aviso, "")
                    if encolar(session, texto, botones):
                        enviadas += enviar_pendientes(session, enviar)
                enviadas += _descansos(session, enviar)
    except Exception as exc:  # noqa: BLE001 — base sin migrar, sin red...
        _avisar_vuelta_fallida(exc)
        _vuelta_sin_base(exc, enviar)
    else:
        _vuelta_con_base(enviar)
    return enviadas


#: Cuánto tiene que durar la falla para decirlo. Un reinicio de Postgres o
#: un parpadeo de la red no merecen mensaje.
MINUTOS_BASE_CAIDA = 10
_base_falla_desde: datetime | None = None
_base_falla_avisada = False


def _vuelta_sin_base(exc: BaseException, enviar, ahora: datetime | None = None) -> None:
    """Con la base caída no se puede encolar nada: el aviso sale directo.
    Antes solo quedaba en el log, y un día sin base se veía igual que un día
    tranquilo (auditoría 2026-11-07, #28)."""
    global _base_falla_desde, _base_falla_avisada
    ahora = ahora or datetime.now()
    if _base_falla_desde is None:
        _base_falla_desde = ahora
    if _base_falla_avisada or ahora - _base_falla_desde < timedelta(minutes=MINUTOS_BASE_CAIDA):
        return
    try:
        enviar(
            f"⚠️ Desde las {_base_falla_desde:%H:%M} no puedo leer la base: {str(exc).splitlines()[0][:150] if str(exc) else type(exc).__name__}\n"
            "Mientras siga así no te llegan avisos y los botones de dinero no funcionan. "
            "¿Está prendida la PC servidor?"
        )
        _base_falla_avisada = True
    except Exception:  # noqa: BLE001 — sin internet tampoco: se intenta en la siguiente vuelta
        logger.debug("No se pudo avisar que la base está caída", exc_info=True)


def _vuelta_con_base(enviar, ahora: datetime | None = None) -> None:
    global _base_falla_desde, _base_falla_avisada
    if _base_falla_avisada and _base_falla_desde is not None:
        ahora = ahora or datetime.now()
        try:
            enviar(f"✅ La base volvió ({ahora:%H:%M}). Los avisos de mientras salen ahora.")
        except Exception:  # noqa: BLE001
            logger.debug("No se pudo avisar que la base volvió", exc_info=True)
    _base_falla_desde = None
    _base_falla_avisada = False


def _descansos(session, enviar) -> int:
    """Vence las solicitudes de descanso sin respuesta y recuerda las que
    siguen esperando. El cambio de estado y el aviso se confirman juntos (lo
    hace `encolar`): si el aviso no entra a la cola, todo vuelve a intentarse
    en la siguiente vuelta en vez de perderse."""
    from pos_uniformes.services import descansos_service, vacaciones_service

    try:
        avisos = descansos_service.tarea_periodica(session)
        if not vacaciones_service.EN_CONSTRUCCION:
            avisos += vacaciones_service.tarea_periodica(session)
    except Exception:  # noqa: BLE001 — base sin migrar: no tumba las alertas
        logger.exception("Descansos: no se pudo revisar la tarea periódica")
        session.rollback()
        return 0
    if not avisos:
        session.commit()  # vencidas sin nada que avisar (no debería pasar)
        return 0
    for texto, botones in avisos:
        if not encolar(session, texto, botones):
            return 0
    return enviar_pendientes(session, enviar)


#: Cada cuánto se escribe en el log que las vueltas están fallando. A DEBUG
#: no se veía nada: una base caída o una migración faltante dejaba las
#: alertas sin salir y el log diciendo que todo iba bien (2026-10-10).
_SEGUNDOS_ENTRE_AVISOS_DE_FALLA = 30 * 60
_ultimo_aviso_de_falla = 0.0


def _avisar_vuelta_fallida(exc: BaseException) -> None:
    import time

    global _ultimo_aviso_de_falla
    ahora = time.time()
    if ahora - _ultimo_aviso_de_falla >= _SEGUNDOS_ENTRE_AVISOS_DE_FALLA:
        _ultimo_aviso_de_falla = ahora
        logger.warning("Alertas: las vueltas están fallando (%s)", exc, exc_info=True)
    else:
        logger.debug("Alertas: vuelta sin efecto (%s)", exc)
