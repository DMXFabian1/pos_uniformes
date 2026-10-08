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
    #: Lo que falta SIN que nadie lo haya decidido. Este es el número que
    #: importa: es el único que puede ser un problema.
    salio: Decimal = Decimal("0.00")
    cortes_que_faltaron: int = 0
    sobro: Decimal = Decimal("0.00")
    cortes_que_sobraron: int = 0
    #: Lo que el dueño bajó (o subió) a mano. Va APARTE desde el 07/10: el
    #: total los sumaba juntos, así que el mensaje distinguía «lo bajaste tú»
    #: de «no cuadra» renglón por renglón y después los volvía a revolver en
    #: una sola cifra. Daniel: «el bot al momento de los cortes no es muy
    #: claro». Lo que él ya decidió no es un faltante.
    ajustado: Decimal = Decimal("0.00")
    cortes_ajustados: int = 0

    @property
    def hay_algo(self) -> bool:
        return bool(self.salio or self.sobro or self.ajustado)


def salidas_del_periodo(session: Session, *, dias: int = 14) -> SalidasPeriodo:
    """Suma las diferencias de todos los cortes del periodo (sin tope)."""
    from pos_uniformes.database.models import LibretaCorte
    from pos_uniformes.services.historial_cortes_service import venta_oficial, venta_real

    desde = date.today() - timedelta(days=int(dias))
    filas = session.scalars(
        select(LibretaCorte).where(LibretaCorte.fecha >= desde)
    ).all()

    salio = sobro = ajustado = Decimal("0.00")
    n_falto = n_sobro = n_ajuste = 0
    total = 0
    for c in filas:
        esperado = Decimal(str(c.monto_esperado or 0))
        # Los cortes viejos no guardaban el esperado: ahí la cifra ERA el total
        # del día. Restarle cero diría que sobraron $20,000 (ver es_legacy).
        if esperado <= 0:
            continue
        total += 1
        dif = (Decimal(str(c.monto_final or 0)) - esperado).quantize(_CENT)
        if not dif:
            continue
        # La misma regla que usa la lista para poner ✏️ en vez de ⚠️. Tiene
        # que ser la misma: si el renglón dice «lo bajaste tú» y el total lo
        # cuenta como faltante, el mensaje se contradice a sí mismo.
        real = venta_real(c)
        if real is not None and real != venta_oficial(c):
            ajustado += dif
            n_ajuste += 1
        elif dif < 0:
            salio += -dif
            n_falto += 1
        else:
            sobro += dif
            n_sobro += 1
    return SalidasPeriodo(
        cortes=total,
        salio=salio.quantize(_CENT),
        cortes_que_faltaron=n_falto,
        sobro=sobro.quantize(_CENT),
        cortes_que_sobraron=n_sobro,
        ajustado=ajustado.quantize(_CENT),
        cortes_ajustados=n_ajuste,
    )


def _pesos(monto: Decimal) -> str:
    """$1,200 — sin centavos cuando son cero.

    En el celular, «.00» repetido doce veces es ruido que hay que saltarse
    para llegar a la cifra."""
    monto = Decimal(monto)
    return f"${monto:,.0f}" if monto == monto.to_integral_value() else f"${monto:,.2f}"


def _renglones_de_corte(c: "CorteFila", dias_abrev) -> list[str]:
    """Un corte en dos renglones: cuánto hubo, y qué pasó con él.

    La cifra va con su etiqueta. Antes salía sola —«$8,420.00»— y para saber
    de qué era había que acordarse (Daniel, 07/10: «no es muy claro»).
    """
    dia = f"{dias_abrev[c.fecha.weekday()]} {c.fecha:%d/%m}"
    if c.diferencia == 0:
        que_paso = "cuadró exacto"
    elif c.ajustado:
        # «lo bajaste tú» y no «ajustado»: quién lo hizo es justo lo que
        # distingue esto de un faltante, y es lo que se perdía.
        verbo = "lo subiste tú" if c.diferencia > 0 else "lo bajaste tú"
        que_paso = f"✏️ {verbo} {_pesos(abs(c.diferencia))}"
        if c.nota:
            que_paso += f" ({c.nota})"
    else:
        señal = "⚠️ " if c.llama_la_atencion else ""
        verbo = "sobraron" if c.diferencia > 0 else "faltaron"
        que_paso = f"{señal}{verbo} {_pesos(abs(c.diferencia))}"
    hora = f" {c.hora}" if c.hora else ""
    return [
        f"{dia}{hora}   {_pesos(c.contado)} en caja",
        f"   {c.quien} · {c.operaciones} ventas · {que_paso}",
    ]


def texto(filas: list[CorteFila], *, dias: int = 14, salidas: SalidasPeriodo | None = None) -> str:
    """Los cortes como se leen en el celular."""
    if not filas:
        return f"No hay cortes en los últimos {dias} días."

    _DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
    lineas = [f"🧾 Cortes · {dias} días", ""]
    for c in filas:
        lineas += _renglones_de_corte(c, _DIAS)

    lineas.append("")
    lineas.append("────────────")
    lineas += _resumen_del_periodo(filas, dias, salidas)
    return "\n".join(lineas)


def _salidas_de_filas(filas) -> SalidasPeriodo:
    """El mismo reparto, pero contando solo los cortes que se enseñan.

    Es el respaldo para cuando no hay acumulado del periodo. La regla de qué
    es ajuste y qué es faltante es la misma de `salidas_del_periodo`, y tiene
    que serlo: dos reglas parecidas acaban discrepando y nadie se entera.
    """
    salio = sobro = ajustado = Decimal("0.00")
    n_falto = n_sobro = n_ajuste = 0
    for c in filas:
        if not c.diferencia:
            continue
        if c.ajustado:
            ajustado += c.diferencia
            n_ajuste += 1
        elif c.diferencia < 0:
            salio += -c.diferencia
            n_falto += 1
        else:
            sobro += c.diferencia
            n_sobro += 1
    return SalidasPeriodo(
        cortes=len(filas),
        salio=salio, cortes_que_faltaron=n_falto,
        sobro=sobro, cortes_que_sobraron=n_sobro,
        ajustado=ajustado, cortes_ajustados=n_ajuste,
    )


def _resumen_del_periodo(filas, dias: int, salidas) -> list[str]:
    """El cierre: de dónde viene cada peso de diferencia.

    Lo importante de aquí es que **lo que el dueño ajustó va aparte de lo que
    no cuadra**. Antes iban sumados en una sola cifra, y esa cifra era la que
    él miraba para saber si tenía un problema: le decía que le faltaban
    $14,515 cuando casi todo eso lo había sacado él mismo.

    Las cuentas son del PERIODO completo, no de los renglones que caben
    arriba. Un número de dinero que depende de cuántos renglones caben en la
    pantalla no sirve para rastrear nada.
    """
    if salidas is None:
        # Sin el acumulado del periodo, se reparten los que se enseñan. Así el
        # cierre dice siempre lo mismo y no hay dos formatos que mantener.
        salidas = _salidas_de_filas(filas)
    if not salidas.hay_algo:
        # Sin nada que repartir, el cierre es una sola frase.
        cuantos = salidas.cortes or len(filas)
        if cuantos == 1:
            return ["Cuadró exacto. 👍"]
        return [f"Los {cuantos} cuadraron exacto. 👍"]

    fuera = salidas.cortes > len(filas)
    cuantos = "1 corte" if salidas.cortes == 1 else f"{salidas.cortes} cortes"
    cabeza = f"De {cuantos} en {dias} días"
    lineas = [f"{cabeza} (no solo los {len(filas)} de arriba):" if fuera else f"{cabeza}:"]

    # El mismo ancho en los tres renglones para que las cifras caigan en
    # columna: en una lista de dinero, comparar es la única razón de leerla.
    partidas = []
    if salidas.cortes_ajustados:
        partidas.append(("Tus ajustes", salidas.ajustado, salidas.cortes_ajustados))
    if salidas.cortes_que_faltaron:
        partidas.append(("Sin explicar", -salidas.salio, salidas.cortes_que_faltaron))
    if salidas.cortes_que_sobraron:
        partidas.append(("Sobró", salidas.sobro, salidas.cortes_que_sobraron))
    # Los que cuadraron van en la misma tabla, sin cifra: es la parte sana del
    # periodo y sin ella las cuentas no suman — se vería «3 con faltante» sin
    # decir nunca contra cuántos buenos.
    cuadraron = salidas.cortes - sum(n for _, _, n in partidas)
    if cuadraron > 0:
        partidas.append(("Cuadraron exacto", None, cuadraron))

    etiqueta = max(len(n) for n, _, _ in partidas)
    ancho = max((len(_pesos(abs(m))) for _, m, _ in partidas if m is not None), default=0)
    for nombre, monto, cuantos in partidas:
        if monto is None:
            cifra = " " * (ancho + 1)
        else:
            signo = "−" if monto < 0 else "+"
            cifra = f"{signo}{_pesos(abs(monto))}".rjust(ancho + 1)
        lineas.append(f"   {nombre.ljust(etiqueta + 2)}{cifra}  en {cuantos}")

    # El renglón que contesta la pregunta: ¿hay un problema o no?
    if salidas.salio:
        lineas.append("")
        lineas.append(
            f"No cuadra sin que tú lo decidieras: {_pesos(salidas.salio)}"
        )
        # La ayuda sale SOLO aquí: es cuando sirve. Repetida en todos los
        # mensajes se vuelve parte del paisaje y deja de leerse.
        lineas.append("   Lo que saques del cajón queda anotado con /retiro 2000 me lo llevé.")

    sin_decir = [c for c in filas if c.ajustado and not c.nota]
    if sin_decir:
        # Se cuenta sobre los que se enseñan y no sobre el periodo, a
        # propósito: la nota es de cada corte y solo se puede leer en los de
        # arriba. Por eso se dice «de los de arriba» y no a secas.
        lineas.append("")
        lineas.append(
            f"{len(sin_decir)} de los de arriba sin anotar por qué."
        )
    return lineas


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
    # Hacer el corte va ARRIBA: esta pantalla solo sabía mirar hacia atrás, y
    # lo que se quiere hacer aquí casi siempre es el de hoy.
    botones = [[("🧾 Hacer el corte de hoy…", f"{PREFIJO}nuevo")]]
    botones += [
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

    def _con_volver(filas):
        return _teclado(list(filas) + [[("‹ Cortes", f"{PREFIJO}lista")]])

    if que == "nuevo":
        # Hacer el corte desde aquí. Esta pantalla solo sabía mirar hacia
        # atrás, y hacer uno era acordarse de /corte o esperar la propuesta
        # de la tarde (Daniel, 2026-10-08).
        import json

        from pos_uniformes.services import corte_remoto_service as crs
        from pos_uniformes.services.telegram_corte_botones_service import (
            botones_de_propuesta,
        )

        with session_factory() as session:
            texto_ = crs.texto_propuesta_corte(session)
            retiro, fondo = crs.cifras_de_propuesta(session)
        teclado = json.loads(botones_de_propuesta(retiro, fondo))
        # Se entra desde «Cortes», así que tiene que haber camino de vuelta:
        # los botones de la propuesta no lo traen porque llega sola.
        teclado["inline_keyboard"].append(
            [{"text": "‹ Cortes", "callback_data": f"{PREFIJO}lista"}]
        )
        return "", texto_, json.dumps(teclado, ensure_ascii=False)

    # Las que siguen van sobre UN corte y necesitan su número. Antes se pedía
    # para todas, y el botón «‹ Cortes» —que no lleva ninguno— contestaba «no
    # conozco ese botón» (visto el 2026-10-08).
    if que in ("ver", "quitar", "borrar", "borrarok"):
        try:
            corte_id = int(crudo)
        except ValueError:
            return "No conozco ese botón", "", ""

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
