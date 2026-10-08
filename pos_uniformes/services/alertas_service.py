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
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

logger = logging.getLogger("alertas")

_CENT = Decimal("0.01")
# Un corte del dueño con más de esto de diferencia se marca con ⚠️.
TOLERANCIA_DIFERENCIA = Decimal("50.00")
# Minutos después del cierre para avisar que no hubo corte.
MINUTOS_SIN_CORTE = 10

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
def encolar(session, texto: str) -> bool:
    """Deja la alerta en la cola. Devuelve False (sin romper) si no se pudo."""
    texto = (texto or "").strip()
    if not texto:
        return False
    try:
        from pos_uniformes.database.models import AlertaTelegram

        session.add(AlertaTelegram(texto=texto, created_at=datetime.now().astimezone()))
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


def enviar_pendientes(session, enviar) -> int:
    """Manda cada alerta pendiente con `enviar(texto)`; marca enviadas. Devuelve cuántas salieron."""
    enviadas = 0
    for alerta in pendientes(session):
        alerta.intentos = int(alerta.intentos or 0) + 1
        try:
            enviar(alerta.texto)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Alerta %s no salió (intento %s): %s", alerta.id, alerta.intentos, exc)
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
    _apertura: object = field(default=None, repr=False)

    def revisar(self, session, ahora: datetime | None = None) -> list[str]:
        """Devuelve los textos a mandar ahora (puede ser vacío)."""
        ahora = _local(ahora or datetime.now().astimezone())
        textos: list[str] = []
        textos += self._movimientos_fuera_de_horario(session, ahora)
        textos += self._cierre_sin_corte(session, ahora)
        textos += self._respaldo_viejo(ahora)
        textos += self._pantalla_apagada(session, ahora)
        return textos

    def _movimientos_fuera_de_horario(self, session, ahora: datetime) -> list[str]:
        from pos_uniformes.database.models import LibretaVenta
        from pos_uniformes.services.horario_tienda_service import hora_apertura, hora_cierre

        if self.ultimo_id is None:
            # Primera vuelta: no reclamar lo viejo, solo marcar dónde vamos.
            self.ultimo_id = int(session.scalar(select(func.coalesce(func.max(LibretaVenta.id), 0))) or 0)
            return []
        rows = list(session.scalars(
            select(LibretaVenta).where(LibretaVenta.id > self.ultimo_id).order_by(LibretaVenta.id)
        ).all())
        textos = []
        for row in rows:
            self.ultimo_id = max(self.ultimo_id, int(row.id))
            momento = _local(row.created_at)
            apertura, cierre = hora_apertura(momento.date()), hora_cierre(momento.date())
            if not (apertura <= momento.time() <= cierre):
                textos.append(texto_fuera_de_horario(row, apertura, cierre))
        return textos

    def _cierre_sin_corte(self, session, ahora: datetime) -> list[str]:
        from pos_uniformes.database.models import LibretaCorte, LibretaVenta
        from pos_uniformes.services.horario_tienda_service import hora_cierre

        hoy = ahora.date()
        if self.dia_sin_corte_avisado == hoy:
            return []
        cierre = hora_cierre(hoy)
        if ahora < datetime.combine(hoy, cierre) + timedelta(minutes=MINUTOS_SIN_CORTE):
            return []
        inicio = datetime.combine(hoy, datetime.min.time()).astimezone()
        hubo_corte = session.scalar(
            select(func.count(LibretaCorte.id)).where(LibretaCorte.fecha == hoy)
        )
        self.dia_sin_corte_avisado = hoy  # se avisa una sola vez al día (o se anota que no hacía falta)
        if hubo_corte:
            return []
        hubo_movimiento = session.scalar(
            select(func.count(LibretaVenta.id)).where(LibretaVenta.created_at >= inicio)
        )
        if not hubo_movimiento:
            return []
        return [texto_sin_corte(hoy, cierre)]


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
        self.dia_respaldo_avisado = hoy
        try:
            from pos_uniformes.services import respaldo_estado_service as est

            estado = est.leer_estado()
            if estado.al_dia:
                return []
            return [est.texto_sin_respaldo(estado)]
        except Exception:  # noqa: BLE001 — el vigilante nunca puede tumbar al bot
            return []


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
        if dia_nuevo:
            # Día nuevo: lo de ayer no se arrastra. Un kiosko apagado anoche
            # no es noticia hoy en la mañana.
            self.dia_de_las_pantallas = hoy
            self.pantallas_vistas_hoy = {}
            self.pantallas_sin_latir = {}
            self.pantallas_avisadas = set()

        hora = ahora.time()
        if not (hora_apertura(hoy) <= hora <= hora_cierre(hoy)):
            return []

        try:
            from pos_uniformes.services import satelite_registry_service as rsvc

            estado = rsvc.listar_con_estado(session, ahora=ahora)
        except Exception:  # noqa: BLE001 — el vigilante nunca tumba al bot
            return []

        if dia_nuevo:
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
            textos.append(
                f"⚠️ {nombre} lleva {int(minutos)} min sin responder, y la tienda "
                "está abierta.\nSi está apagada, ahí no se puede cotizar ni vender."
            )
        return textos


def procesar(session_factory, enviar, vigilante: Vigilante | None = None) -> int:
    """Una vuelta completa: manda la cola y lo que vea el vigilante. Nunca truena."""
    enviadas = 0
    try:
        with session_factory() as session:
            enviadas += enviar_pendientes(session, enviar)
            if vigilante is not None:
                for texto in vigilante.revisar(session):
                    if encolar(session, texto):
                        enviadas += enviar_pendientes(session, enviar)
    except Exception as exc:  # noqa: BLE001 — base sin migrar, sin red...
        logger.debug("Alertas: vuelta sin efecto (%s)", exc)
    return enviadas
