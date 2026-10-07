"""Los últimos cortes, con lo que faltó o sobró.

Un corte con $300 de diferencia no enteraba a nadie hasta que alguien lo
buscaba en la PC (Daniel, 2026-09-25: "lo principal son los cortes y el
dinero"). Esto lo pone en el celular.

La diferencia es siempre **contado − esperado**: positiva sobró, negativa
faltó. Misma cuenta que el resumen de la noche.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

_CENT = Decimal("0.01")

#: Cuántos cortes caben en un mensaje de celular sin volverse un muro.
TOPE = 10

#: A partir de aquí una diferencia deja de ser "redondeo" y merece mirarse.
OJO = Decimal("50.00")


@dataclass(frozen=True)
class CorteFila:
    fecha: date
    hora: str
    quien: str
    contado: Decimal
    esperado: Decimal
    operaciones: int
    #: El dueño bajó (o subió) la cifra a mano con «Ajustar la venta».
    ajustado: bool = False
    #: Por qué se ajustó. Vacío en los de antes de que se pidiera.
    nota: str = ""
    #: Para poder tocarlo desde Telegram. Va al final y con valor por omisión
    #: para no obligar a nadie que ya armaba filas a mano.
    id: int = 0

    @property
    def diferencia(self) -> Decimal:
        return (self.contado - self.esperado).quantize(_CENT)

    @property
    def llama_la_atencion(self) -> bool:
        """Un ajuste del dueño no es un descuadre: él mismo lo puso.

        Lo que merece mirarse es cuando la caja no cuadra sin que nadie lo
        haya decidido (Daniel, 2026-10-01: esos 'faltó $2,000' eran sus
        ajustes, no dinero perdido)."""
        return not self.ajustado and abs(self.diferencia) >= OJO


def _quien(code: str) -> str:
    from pos_uniformes.services.nombres_empleadas_service import mostrar

    return mostrar(code)


def ultimos(session: Session, *, dias: int = 14, tope: int = TOPE) -> list[CorteFila]:
    """Los cortes más recientes, del más nuevo al más viejo."""
    from pos_uniformes.database.models import LibretaCorte
    from pos_uniformes.services.historial_cortes_service import venta_oficial, venta_real

    desde = date.today() - timedelta(days=int(dias))
    filas = session.scalars(
        select(LibretaCorte)
        .where(LibretaCorte.fecha >= desde)
        .order_by(LibretaCorte.fecha.desc(), LibretaCorte.id.desc())
        .limit(int(tope))
    ).all()

    salida = []
    for c in filas:
        momento = c.hasta or c.created_at
        momento = momento.astimezone() if momento and momento.tzinfo else momento
        salida.append(
            CorteFila(
                id=int(c.id),
                fecha=c.fecha,
                hora=momento.strftime("%H:%M") if momento else "",
                quien=_quien(str(c.creado_por or "")),
                contado=Decimal(str(c.monto_final or 0)),
                esperado=Decimal(str(c.monto_esperado or 0)),
                operaciones=int(c.operaciones or 0),
                ajustado=bool(venta_real(c) is not None and venta_real(c) != venta_oficial(c)),
                nota=str(c.nota or ""),
            )
        )
    return salida


@dataclass(frozen=True)
class SalidasPeriodo:
    """Lo que salió (y sobró) por diferencia en TODO el periodo.

    Va aparte de `ultimos()` a propósito: la lista se corta en `TOPE` para que
    el mensaje no sea un muro, y sumar solo lo que se alcanza a enseñar daría
    un total más chico que el real. Un número de dinero que depende de cuántos
    renglones caben en la pantalla no sirve para rastrear nada.
    """

    cortes: int = 0
    salio: Decimal = Decimal("0.00")
    cortes_que_faltaron: int = 0
    sobro: Decimal = Decimal("0.00")
    cortes_que_sobraron: int = 0


def salidas_del_periodo(session: Session, *, dias: int = 14) -> SalidasPeriodo:
    """Suma las diferencias de todos los cortes del periodo (sin tope)."""
    from pos_uniformes.database.models import LibretaCorte

    desde = date.today() - timedelta(days=int(dias))
    filas = session.scalars(
        select(LibretaCorte).where(LibretaCorte.fecha >= desde)
    ).all()

    salio = sobro = Decimal("0.00")
    n_falto = n_sobro = 0
    total = 0
    for c in filas:
        esperado = Decimal(str(c.monto_esperado or 0))
        # Los cortes viejos no guardaban el esperado: ahí la cifra ERA el total
        # del día. Restarle cero diría que sobraron $20,000 (ver es_legacy).
        if esperado <= 0:
            continue
        total += 1
        dif = (Decimal(str(c.monto_final or 0)) - esperado).quantize(_CENT)
        if dif < 0:
            salio += -dif
            n_falto += 1
        elif dif > 0:
            sobro += dif
            n_sobro += 1
    return SalidasPeriodo(
        cortes=total,
        salio=salio.quantize(_CENT),
        cortes_que_faltaron=n_falto,
        sobro=sobro.quantize(_CENT),
        cortes_que_sobraron=n_sobro,
    )


def texto(filas: list[CorteFila], *, dias: int = 14, salidas: SalidasPeriodo | None = None) -> str:
    """Los cortes como se leen en el celular."""
    if not filas:
        return f"No hay cortes en los últimos {dias} días."

    _DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
    lineas = [f"🧾 Últimos cortes ({len(filas)}):", ""]
    cuadrados = 0
    for c in filas:
        dia = f"{_DIAS[c.fecha.weekday()]} {c.fecha:%d/%m}"
        if c.diferencia == 0:
            cuadrados += 1
            marca = "✅ cuadró"
        elif c.ajustado:
            signo = "+" if c.diferencia > 0 else "−"
            marca = f"✏️ ajustado {signo}${abs(c.diferencia):,.2f}"
            if c.nota:
                marca += f" · {c.nota}"
        else:
            señal = "⚠️" if c.llama_la_atencion else "·"
            verbo = "sobró" if c.diferencia > 0 else "faltó"
            marca = f"{señal} {verbo} ${abs(c.diferencia):,.2f}"
        lineas.append(f"{dia} {c.hora} · ${c.contado:,.2f} — {marca}")
        lineas.append(f"   {c.quien} · {c.operaciones} ops")

    ojo = [c for c in filas if c.llama_la_atencion]
    lineas.append("")
    if ojo:
        peor = max(ojo, key=lambda c: abs(c.diferencia))
        lineas.append(
            f"{len(ojo)} de {len(filas)} se pasan de ${OJO:,.0f}. "
            f"El más: {peor.fecha:%d/%m} con ${abs(peor.diferencia):,.2f}."
        )
        # Lo que se ajusta a mano no entra aquí: eso lo decidió el dueño.
    elif salidas is not None and (salidas.salio or salidas.sobro):
        # NO va el 👍. Aquí «ajustado» significa solo «tuvo diferencia», así que
        # nada llama la atención nunca y el mensaje felicitaba («ninguno se pasa
        # de $50 👍») justo encima del renglón que decía que habían salido
        # $14,825. Un visto bueno que sale pase lo que pase no informa nada, y
        # enseña a no leer el que sí importa (2026-10-04).
        lineas.append(f"{cuadrados} de {len(filas)} cuadraron exacto.")
    else:
        lineas.append(f"{cuadrados} cuadraron exacto y ninguno se pasa de ${OJO:,.0f}. 👍")
    # El total con el que Daniel rastrea su dinero. Antes sumaba SOLO los
    # cortes que caben en el mensaje (tope de 10), así que en un periodo largo
    # decía menos de lo que de verdad salió: un número de dinero que depende
    # de cuántos renglones caben en la pantalla no sirve para rastrear nada
    # ("sólo necesito que sea trazable para mí", 2026-10-04). `salidas` lo trae
    # calculado sobre TODOS los cortes del periodo.
    if salidas is not None and (salidas.salio or salidas.sobro):
        neto = salidas.sobro - salidas.salio
        cuantos = salidas.cortes_que_faltaron + salidas.cortes_que_sobraron
        # Solo se aclara "no solo los de arriba" cuando de verdad hay más de
        # los que caben: si no, es ruido.
        alcance = (
            f"{dias} días, no solo los {len(filas)} de arriba"
            if salidas.cortes > len(filas)
            else f"{dias} días"
        )
        lineas.append(
            f"{cuantos} de {salidas.cortes} con diferencia, "
            f"{'−' if neto < 0 else '+'}${abs(neto):,.2f} en total ({alcance})."
        )
        if salidas.salio and salidas.sobro:
            lineas.append(f"   Salió ${salidas.salio:,.2f} · sobró ${salidas.sobro:,.2f}")
        lineas.append("   Lo que saques del cajón queda anotado con /retiro 2000 me lo llevé.")
    else:
        ajustados = [c for c in filas if c.ajustado]
        if ajustados:
            suma = sum((c.diferencia for c in ajustados), Decimal("0"))
            lineas.append(f"{len(ajustados)} con ajuste tuyo, {'−' if suma < 0 else '+'}${abs(suma):,.2f} en total.")

    # Esto se cuenta sobre los que se enseñan y no sobre el periodo, a
    # propósito: la nota es de cada corte y solo se puede leer en los que
    # están arriba.
    sin_decir = [c for c in filas if c.ajustado and not c.nota]
    if sin_decir:
        lineas.append(f"{len(sin_decir)} de ellos sin decir por qué (son de antes).")
    return "\n".join(lineas)


def resumen(session: Session, *, dias: int = 14) -> str:
    return texto(
        ultimos(session, dias=dias), dias=dias, salidas=salidas_del_periodo(session, dias=dias)
    )


# ── Tocar un corte: quitarle el ajuste o borrarlo ────────────────────────────
#
# El diálogo «Cortes anteriores» del kiosko sabe ajustar la cifra, quitar el
# ajuste y borrar un corte, y nada de eso estaba en el bot (Daniel, 2026-10-04).
# Borrar va con DOS toques a propósito: es lo único de aquí que no se puede
# deshacer, y se hace con el teléfono en la mano, en la calle.

PREFIJO = "co:"


def es_de_cortes(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def _teclado(filas):
    from pos_uniformes.services import telegram_service

    return telegram_service.teclado(filas)


def dias_de_argumento(argumento: str, *, por_defecto: int = 14, tope: int = 180) -> int:
    """`/cortes 30` = los últimos 30 días. Para rastrear el dinero hay que poder
    mirar más atrás que la quincena que trae por defecto."""
    texto_arg = str(argumento or "").strip()
    if not texto_arg.isdigit():
        return por_defecto
    return max(1, min(int(texto_arg), tope))


def texto_y_botones(session: Session, *, dias: int = 14, argumento: str = "") -> tuple[str, str]:
    """La lista de siempre, con un botón por corte para poder tocarlo."""
    if argumento:
        dias = dias_de_argumento(argumento, por_defecto=dias)
    filas = ultimos(session, dias=dias)
    botones = [
        [(f"{c.fecha:%d/%m} · ${c.contado:,.0f}" + (" ✏️" if c.ajustado else ""),
          f"{PREFIJO}ver:{c.id}")]
        for c in filas
    ]
    botones.append([("‹ Menú", "m:raiz")])
    return (
        texto(filas, dias=dias, salidas=salidas_del_periodo(session, dias=dias)),
        _teclado(botones),
    )


def detalle(session: Session, corte_id: int) -> tuple[str, list]:
    """(texto, filas de botones) de UN corte."""
    from pos_uniformes.database.models import LibretaCorte
    from pos_uniformes.services.historial_cortes_service import venta_oficial, venta_real

    corte = session.get(LibretaCorte, int(corte_id))
    if corte is None:
        return "Ese corte ya no existe.", []

    oficial = venta_oficial(corte)
    real = venta_real(corte)
    lineas = [
        f"🧾 Corte del {corte.fecha:%d/%m/%Y}",
        f"Lo que dice el ticket: ${oficial:,.2f}",
    ]
    if real is not None and real != oficial:
        lineas.append(f"Lo que de verdad se vendió: ${real:,.2f}")
        lineas.append(f"Ajuste tuyo: {'−' if oficial < real else '+'}${abs(oficial - real):,.2f}")
        lineas.append(f"Por qué: {corte.nota}" if corte.nota else "Sin decir por qué.")
    lineas.append("")
    lineas.append(f"Para cambiar la cifra:\n/ajustar {corte.id} 12500 depósito al banco")

    filas = []
    if real is not None and real != oficial:
        filas.append([("↩️ Quitar el ajuste", f"{PREFIJO}quitar:{corte.id}")])
    filas.append([("🗑 Borrar este corte", f"{PREFIJO}borrar:{corte.id}")])
    return "\n".join(lineas), filas


def atender(dato: str, *, session_factory, quien: str) -> tuple[str, str, str]:
    """Un botón de cortes: (aviso corto, texto nuevo, botones nuevos)."""
    from pos_uniformes.services import historial_cortes_service as hist

    accion = str(dato or "")[len(PREFIJO):]
    que, _, crudo = accion.partition(":")
    try:
        corte_id = int(crudo)
    except ValueError:
        return "No conozco ese botón", "", ""

    def _con_volver(filas):
        return _teclado(list(filas) + [[("‹ Cortes", f"{PREFIJO}lista")]])

    if que == "ver":
        with session_factory() as session:
            texto_, filas = detalle(session, corte_id)
        return "", texto_, _con_volver(filas)

    if que == "quitar":
        with session_factory() as session:
            try:
                hist.quitar_ajuste(session, corte_id, creado_por=quien)
                session.commit()
                aviso = "Ajuste quitado"
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                aviso = str(exc)[:60]
            texto_, filas = detalle(session, corte_id)
        return aviso, texto_, _con_volver(filas)

    if que == "borrar":
        # Primer toque: solo pregunta. Borrar un corte no se deshace.
        with session_factory() as session:
            texto_, _ = detalle(session, corte_id)
        texto_ += "\n\n⚠️ Borrarlo no se puede deshacer."
        return "", texto_, _con_volver(
            [[("Sí, bórralo", f"{PREFIJO}borrarok:{corte_id}")],
             [("Mejor no", f"{PREFIJO}ver:{corte_id}")]]
        )

    if que == "borrarok":
        with session_factory() as session:
            try:
                hist.borrar_corte(session, corte_id, creado_por=quien)
                session.commit()
                aviso = "Borrado"
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                aviso = str(exc)[:60]
            texto_, botones = texto_y_botones(session)
        return aviso, texto_, botones

    with session_factory() as session:
        texto_, botones = texto_y_botones(session)
    return "", texto_, botones


def esconder_tarjetas(session: Session, argumento: str, *, quien: str) -> str:
    """`/sintarjeta <id>`: esconde los cobros con tarjeta de un corte ya hecho.

    Va aparte de `/ajustar` a propósito. Ajustar la cifra y esconder las
    tarjetas son dos decisiones distintas; si ajustar escondiera de paso, cada
    corrección de una cifra se llevaría cosas sin que nadie lo pidiera. Esto
    existe porque el día del corte se puede olvidar —o escribir mal— y lo que
    quedó visible se queda visible para siempre (Daniel, 2026-10-07).
    """
    from pos_uniformes.database.models import LibretaCorte
    from pos_uniformes.services.historial_cortes_service import periodo_del_corte
    from pos_uniformes.services.libreta_service import marcar_privadas_del_periodo

    crudo = (argumento or "").strip()
    if not crudo.isdigit():
        return (
            "Se usa así:\n/sintarjeta 12\n\n"
            "El número de corte sale en /cortes, tocando el que sea."
        )
    corte = session.get(LibretaCorte, int(crudo))
    if corte is None:
        return "Ese corte ya no existe."
    try:
        desde, hasta = periodo_del_corte(session, corte)
        cuantos = marcar_privadas_del_periodo(session, desde, hasta, creado_por=quien)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return str(exc)
    if not cuantos:
        return (
            f"El corte {corte.id} ({corte.fecha:%d/%m}) no tiene cobros con tarjeta "
            "visibles: o no hubo, o ya estaban escondidos."
        )
    return (
        f"✅ Escondí {cuantos} cobro(s) con tarjeta del corte {corte.id} "
        f"({corte.fecha:%d/%m}).\n"
        "El ticket que ya se imprimió no cambia; esto es para lo que se ve de aquí "
        "en adelante."
    )


def ajustar(session: Session, argumento: str, *, quien: str) -> str:
    """`/ajustar <id> <cifra> <por qué>`. El motivo es obligatorio si mueve dinero."""
    from decimal import InvalidOperation

    from pos_uniformes.services import historial_cortes_service as hist

    partes = (argumento or "").split(maxsplit=2)
    if len(partes) < 2:
        return (
            "Se usa así:\n/ajustar 12 12500 depósito al banco\n\n"
            "El número de corte sale en /cortes, tocando el que sea."
        )
    try:
        corte_id = int(partes[0])
        cifra = Decimal(partes[1].replace("$", "").replace(",", ""))
    except (ValueError, InvalidOperation):
        return "No entendí. Se usa así:\n/ajustar 12 12500 depósito al banco"
    nota = partes[2].strip() if len(partes) > 2 else ""
    try:
        hist.ajustar_corte(session, corte_id, venta=cifra, creado_por=quien, nota=nota)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return str(exc)
    return f"✅ El corte {corte_id} ahora dice ${cifra:,.2f}." + (
        f"\nPor qué: {nota}" if nota else ""
    )
