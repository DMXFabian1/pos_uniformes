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

    Cada botón dice **lo que va a pasar al tocarlo**, y los que abren otra
    pantalla terminan en «…». Antes decían «Retirar otra cantidad» y «Cambiar
    el fondo», que suenan a ajustar un dato y volver, cuando en realidad
    llevan a una pantalla donde cualquier cifra cierra el corte de una
    (Daniel, 07/10: «esas opciones son poco claras»).
    """
    return _teclado(
        [
            # La cifra va EN el botón: es la del mensaje, y tenerla a la mano
            # al momento de tocar es lo que hace que no haya que releer.
            [(f"✅ Hacer el corte y sacar {_pesos(retiro)}", f"{PREFIJO}ok")],
            # «Bajarle a la venta» y no «sacar otra cantidad»: es la misma
            # operación preguntada por el lado que Daniel la piensa. Él sabe
            # cuánto quiere bajar —lo de tarjeta, un depósito—, no cuánto
            # queda de retiro; y así se llama después en la lista de cortes,
            # «lo bajaste tú $1,200» (07/10).
            [("✂️ Bajarle a la venta…", f"{PREFIJO}bajar"),
             ("🪙 Dejar otro fondo…", f"{PREFIJO}fondo")],
            # «Algo no salió del cajón» era una negación y no decía qué iba a
            # pasar. Esto es lo que se va a hacer: apuntarlo.
            [("➖ Apuntar algo que ya salió del cajón", f"{PREFIJO}cajon")],
            [("🚫 Hoy no", f"{PREFIJO}no")],
        ]
    )


def _cantidades(tope: Decimal) -> list[int]:
    """Las de siempre que caben, de mayor a menor."""
    return [c for c in sorted(DE_SIEMPRE, reverse=True) if Decimal(c) <= tope]


def pantalla_bajar(retiro: Decimal, tarjeta: Decimal) -> tuple[str, str]:
    """(texto, botones) para bajarle una cantidad a la venta del corte.

    `retiro` es lo que saldría tal cual: es el tope, porque bajar más que eso
    dejaría la venta del papel por debajo de lo que ya salió del cajón.

    Cada botón hace el corte, así que cada uno lo dice. Lo de tarjeta va
    primero porque es lo que más se baja.
    """
    filas = [[("✅ Nada, el corte tal cual", f"{PREFIJO}ok")]]
    ofrecidas: list[int] = []
    if 0 < tarjeta <= retiro:
        entero = int(tarjeta)
        ofrecidas.append(entero)
        filas.append([(
            f"Bajar {_pesos(tarjeta)}  (lo de tarjeta)", f"{PREFIJO}baja:{entero}"
        )])
    for c in sorted(DE_SIEMPRE):
        if Decimal(c) > retiro or c in ofrecidas:
            continue
        filas.append([(f"Bajar {_pesos(c)}", f"{PREFIJO}baja:{c}")])
    filas.append([("‹ Volver", f"{PREFIJO}volver")])

    texto = [
        "¿Cuánto le bajo a la venta?",
        "",
        "Lo que bajes no aparece en el ticket de la tienda.",
        "Cada botón hace el corte con esa cantidad ya restada.",
        "",
        "Para una cifra exacta o con motivo:",
        "/corte 5000 fondo 2000 deposité al banco",
    ]
    return "\n".join(texto), _teclado(filas)


def pantalla_cantidades(que: str, sugerida: Decimal, tope: Decimal) -> tuple[str, str]:
    """(texto, botones) para elegir cuánto sacar o cuánto dejar de fondo.

    Cada cifra cierra el corte al tocarla, así que **el botón lo dice**: no
    «$5,000» sino «Hacer el corte sacando $5,000». Antes la advertencia vivía
    en el texto de arriba, escrita `**hace el corte**` — y como el bot manda
    sin formato, los asteriscos salían a la vista y la única advertencia del
    flujo se leía como basura (07/10).
    """
    accion = "ret" if que == "retirar" else "fnd"
    if que == "retirar":
        titulo = "¿Cuánto sacas del cajón?"
        def etiqueta(monto: str) -> str:
            return f"Hacer el corte sacando {monto}"
    else:
        titulo = "¿Cuánto se queda para mañana?"
        def etiqueta(monto: str) -> str:
            return f"Hacer el corte dejando {monto}"

    filas = []
    if sugerida > 0:
        filas.append([(
            f"✅ {etiqueta(_pesos(sugerida))}  (lo calculado)",
            f"{PREFIJO}{accion}:{int(sugerida)}",
        )])
    for c in _cantidades(tope):
        if Decimal(c) == sugerida.quantize(Decimal("1")):
            continue
        # Uno por renglón: tres cifras sueltas en fila se tocan sin leer, y
        # aquí cada toque hace el corte.
        filas.append([(etiqueta(_pesos(c)), f"{PREFIJO}{accion}:{c}")])
    filas.append([("‹ Volver", f"{PREFIJO}volver")])

    texto = [
        titulo,
        "",
        "Cada botón hace el corte con esa cantidad.",
        "",
        "Para las dos cosas a la vez, o con un motivo:",
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

    # «retirar» ya no se ofrece, pero se sigue atendiendo: los mensajes viejos
    # se quedan en el chat con sus botones, y tocar uno no debe contestar «no
    # conozco ese botón».
    if accion in ("bajar", "retirar", "fondo", "volver"):
        with session_factory() as session:
            texto, botones = _pantalla(session, accion)
        return "", texto, botones

    if accion in ("ok", "ret", "fnd", "baja"):
        retirar = fondo = None
        if accion == "ret":
            retirar = _cifra(crudo)
        elif accion == "fnd":
            fondo = _cifra(crudo)
        elif accion == "baja":
            # Bajar y retirar son la misma palanca por lados distintos: lo que
            # se baja de la venta es lo que deja de salir del cajón.
            cuanto = _cifra(crudo)
            if cuanto is not None:
                with session_factory() as session:
                    calculado, _ = crs.cifras_de_propuesta(session)
                retirar = max(calculado - cuanto, Decimal("0.00"))
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
    if accion in ("bajar", "retirar"):
        return pantalla_bajar(retiro, crs.tarjeta_del_periodo(session, ahora))
    return pantalla_cantidades("fondo", fondo, max(retiro, fondo))
