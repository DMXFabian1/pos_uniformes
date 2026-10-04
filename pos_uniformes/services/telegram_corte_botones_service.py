"""Los botones de la propuesta del corte.

Daniel (2026-10-04): *"¿cómo harías más sencilla esta interacción con el bot?"*.

La respuesta no era otro comando: el bot ya tiene 31, y ese mismo día le agregué
uno con cuatro palabras que hay que recordar (`/corte 5000 fondo 2000 otros 350
nota`). El menú arregló **mirar** cosas; **hacer** cosas seguía siendo escribir.

Esta propuesta llega todas las tardes y contestarla es lo que más se hace con el
bot. Que traiga sus botones es lo que más veces al día ahorra escribir — el
mismo patrón que ya funcionó con el aviso del préstamo: **la decisión se toma
donde llega el mensaje**, no acordándose de un comando y volviendo a buscar.

Sin estado a propósito
----------------------
Telegram no guarda nada entre toques, así que cada botón lleva todo lo que
necesita en su propio dato y **hace el corte de una**. Juntar retiro y fondo en
la misma operación pediría recordar lo que se tocó antes; para eso sigue estando
`/corte 5000 fondo 2000`, que es justo el caso raro. Lo común —hacerlo tal cual,
o retirar una cifra— queda en un toque o dos.
"""

from __future__ import annotations

from decimal import Decimal

#: Prefijo de los botones de esta pantalla.
PREFIJO = "cc:"

#: Cantidades de siempre para retirar o dejar de fondo. Se filtran a las que
#: caben, y la cifra calculada va primero: casi siempre es la que se usa.
DE_SIEMPRE = (500, 1000, 2000, 3000, 5000)


def _teclado(filas):
    from pos_uniformes.services import telegram_service

    return telegram_service.teclado(filas)


def _pesos(valor: Decimal | int) -> str:
    return f"${Decimal(valor):,.0f}"


def botones_de_propuesta(retiro: Decimal, fondo: Decimal) -> str:
    """Los botones que acompañan a «¿Hacemos el corte?».

    `retiro` es lo que saldría del cajón tal cual, y `fondo` lo que quedaría.
    """
    return _teclado(
        [
            [("✅ Hacer el corte", f"{PREFIJO}ok")],
            [("💵 Retirar otra cantidad", f"{PREFIJO}retirar"),
             ("💰 Cambiar el fondo", f"{PREFIJO}fondo")],
            [("🔎 Algo no salió del cajón", f"{PREFIJO}cajon")],
            [("🙅 Hoy no", f"{PREFIJO}no")],
        ]
    )


def _cantidades(tope: Decimal) -> list[int]:
    """Las de siempre que caben, de mayor a menor."""
    return [c for c in sorted(DE_SIEMPRE, reverse=True) if Decimal(c) <= tope]


def pantalla_cantidades(que: str, sugerida: Decimal, tope: Decimal) -> tuple[str, str]:
    """(texto, botones) para elegir cuánto retirar o cuánto dejar de fondo."""
    accion = "ret" if que == "retirar" else "fnd"
    titulo = (
        "¿Cuánto se retira del cajón?" if que == "retirar"
        else "¿Cuánto se queda de fondo?"
    )
    filas = []
    if sugerida > 0:
        filas.append([(f"{_pesos(sugerida)}  (lo calculado)", f"{PREFIJO}{accion}:{int(sugerida)}")])
    fila: list = []
    for c in _cantidades(tope):
        if Decimal(c) == sugerida.quantize(Decimal("1")):
            continue
        fila.append((_pesos(c), f"{PREFIJO}{accion}:{c}"))
        if len(fila) == 3:
            filas.append(fila)
            fila = []
    if fila:
        filas.append(fila)
    filas.append([("‹ Volver", f"{PREFIJO}volver")])

    texto = [
        titulo,
        "",
        "Tocar una cantidad **hace el corte** con ella.",
        "",
        "Para juntar las dos cosas o poner un motivo:",
        "/corte 5000 fondo 2000 deposité al banco",
    ]
    return "\n".join(texto), _teclado(filas)


def es_de_corte(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def atender(dato: str, *, session_factory, quien: str) -> tuple[str, str, str]:
    """Un botón de la propuesta: (aviso corto, texto nuevo, botones nuevos)."""
    from pos_uniformes.services import corte_remoto_service as crs
    from pos_uniformes.services.corte_caja_service import estado_caja, pagos_que_tocan_hoy

    accion, _, crudo = str(dato or "")[len(PREFIJO):].partition(":")

    if accion == "no":
        from pos_uniformes.services.corte_propuesta_service import cancelar

        if cancelar():
            return "Hoy no", "Ok, hoy no se hace el corte.\n\nCuando quieras, /corte.", ""
        return "", "No hay ningún corte propuesto hoy. Si lo quieres hacer, /corte.", ""

    if accion == "cajon":
        from pos_uniformes.services import telegram_cajon_service as cj

        with session_factory() as session:
            texto, botones = cj.texto_y_botones(session)
        return "", texto + "\n\nCuando termines, vuelve con /corte.", botones

    if accion in ("retirar", "fondo", "volver"):
        with session_factory() as session:
            texto, botones = _pantalla(session, accion)
        return "", texto, botones

    if accion in ("ok", "ret", "fnd"):
        retirar = fondo = None
        if accion == "ret":
            retirar = _cifra(crudo)
        elif accion == "fnd":
            fondo = _cifra(crudo)
        if accion != "ok" and (retirar is None and fondo is None):
            return "No conozco ese botón", "", ""
        with session_factory() as session:
            resultado = crs.hacer_corte_y_avisar(
                session, creado_por=quien, retirar=retirar, fondo=fondo
            )
            session.commit()
        return ("Corte hecho" if resultado.hecho else ""), resultado.mensaje, ""

    return "No conozco ese botón", "", ""


def _cifra(crudo: str) -> Decimal | None:
    try:
        return Decimal(str(crudo)).quantize(Decimal("0.01"))
    except Exception:  # noqa: BLE001
        return None


def _pantalla(session, accion: str) -> tuple[str, str]:
    """La pantalla de cantidades, o la propuesta de vuelta."""
    from datetime import datetime

    from pos_uniformes.services import corte_remoto_service as crs

    ahora = datetime.now().astimezone()
    retiro, fondo = crs.cifras_de_propuesta(session, ahora)

    if accion == "volver":
        return crs.texto_propuesta_corte(session, ahora), botones_de_propuesta(retiro, fondo)
    if accion == "retirar":
        return pantalla_cantidades("retirar", retiro, retiro)
    return pantalla_cantidades("fondo", fondo, max(retiro, fondo))
