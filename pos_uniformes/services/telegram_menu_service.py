"""El menú del bot: tocar en vez de recordar.

Son 19 comandos y Daniel pidió la chuleta justamente porque se le olvidan
(2026-09-25). El menú los pone a un toque, y el mensaje se reescribe en su
lugar en vez de llenar el chat: se entra, se ve, se vuelve.

Lo que mueve dinero **no** queda a un toque: pagar pide el segundo toque sobre
el desglose, igual que por texto pide la palabra de más. El corte y el retiro
no están aquí a propósito — llevan cantidad y motivo, y eso se escribe.
"""

from __future__ import annotations

from decimal import Decimal

from datetime import date

#: Prefijo de los datos que viajan en los botones (máx. 64 bytes por regla de Telegram).
PREFIJO = "m:"

# Eran quince botones en diez renglones y dos decían lo que ya estaba dicho
# (Daniel, 2026-10-08: «son muchos botones y creo que algunos hacen lo mismo»):
#
# - «Hoy» mandaba EXACTAMENTE la cabecera de este menú: las dos salen de
#   `texto_hoy()`. Tocarlo reescribía el párrafo que ya se estaba leyendo.
# - «Pendientes» es una sección de «Resumen», con el mismo texto.
#
# «¿Todo en pie?» también repite lo vendido y el último corte, pero agrega
# pantallas, respaldo y cola de impresión: ése sí se gana su renglón.
_RAIZ = [
    [("🫀 ¿Todo en pie?", "m:pulso")],
    [("💵 Caja", "m:estado"), ("📋 Resumen", "m:resumen")],
    [("🧾 Cortes", "m:cortes"), ("💰 Pagos", "m:pagos"), ("💼 Mi pago", "mp:ver")],
    [("💵 Lo que salió del cajón", "m:cajon")],
    [("👥 Las muchachas…", "m:gente"), ("🏪 Qué contar", "m:contar")],
    [("🔎 Sin surtir", "m:faltas"), ("📣 Avisos", "m:avisos")],
    [("⭐ Programas", "m:programas"), ("❔ Ayuda", "m:ayuda")],
]

#: Lo de ellas, junto. Ninguno es de diario, y sueltos ocupaban tres renglones
#: del tablero. Pagos NO entra aquí: ése sí se usa seguido y se queda arriba.
_GENTE = [
    [("👥 Quién vino", "m:asistencia")],
    [("💵 Préstamos", "m:prestamos")],
    [("🛌 Días de descanso", "m:descansos"), ("🏖️ Vacaciones", "m:vacaciones")],
]


def _gente():
    """Las filas de «Las muchachas…». Vacaciones solo si ya se estrenó."""
    from pos_uniformes.services import vacaciones_service as vs

    if not vs.EN_CONSTRUCCION:
        return _GENTE
    return [[b for b in fila if b[1] != "m:vacaciones"] for fila in _GENTE]


def _teclado(filas):
    from pos_uniformes.services import telegram_service

    return telegram_service.teclado(filas)


def botones_raiz() -> str:
    """Los botones del tablero, para pegarlos debajo de otro mensaje (la
    ayuda corta, 2026-11-20). Son los mismos callbacks `m:…` de siempre."""
    return _teclado(_RAIZ)


def menu_raiz(session=None, *, hoy: date | None = None) -> tuple[str, str]:
    """(texto, botones) del tablero.

    No pregunta «¿qué quieres ver?»: llega con el día ya puesto. Abrir el menú
    y saber cómo va la tienda tiene que ser el mismo gesto (Daniel, 2026-09-25:
    "que sea increíblemente completo y fácil de usar")."""
    if session is None:
        return _sin_dia(hoy), _teclado(_RAIZ)
    return cabecera(session, hoy=hoy), _teclado(_RAIZ)


#: La pregunta con la que cierra el tablero.
PREGUNTA = "¿Qué quieres ver?"


def _titulo(hoy: date | None = None) -> str:
    """«📋 TIENDA · vie 20 nov · 14:30»: el encabezado del menú fijado
    (formato común del bot, 2026-11-20). La hora dice qué tan fresco está:
    el tablero se reescribe solo cada tantos minutos."""
    from datetime import datetime

    from pos_uniformes.services.telegram_formato import encabezado

    ahora = datetime.now()
    if hoy is None or hoy == ahora.date():
        return encabezado("📋", "Tienda", ahora, hora=True)
    return encabezado("📋", "Tienda", hoy)


def _sin_dia(hoy: date | None = None) -> str:
    """El tablero cuando no se pudo leer el día: encabezado y la pregunta."""
    return _titulo(hoy) + "\n" + PREGUNTA


def _sin_su_encabezado(texto: str) -> str:
    """`texto_hoy()` trae su propio encabezado («📅 Hoy · …»); en el tablero
    manda el de la tienda, así que el suyo se quita (2026-11-20)."""
    from pos_uniformes.services.telegram_formato import es_encabezado

    lineas = texto.splitlines()
    if lineas and (lineas[0].startswith("📅") or es_encabezado(lineas[0])):
        lineas = lineas[1:]
    while lineas and not lineas[0].strip():
        lineas = lineas[1:]
    return "\n".join(lineas)


def cabecera(session, *, hoy: date | None = None) -> str:
    """El día de un vistazo, para encabezar el tablero.

    Si algo falla al leerlo, el menú sigue sirviendo: los botones son lo que
    no puede faltar."""
    try:
        from pos_uniformes.services import asistencia_service as asis
        from pos_uniformes.services.resumen_diario_service import recolectar, texto_hoy

        datos = recolectar(session, hoy)
        estan = [
            a.nombre for a in asis.asistencia_del_dia(session, hoy)
            if a.estado == asis.PRESENTE
        ]
        texto = texto_hoy(datos, quien_esta=estan)
    except Exception:  # noqa: BLE001 — el tablero no puede quedarse sin botones
        return _sin_dia(hoy)
    cuerpo = _sin_su_encabezado(texto)
    texto = _titulo(hoy) + ("\n" + cuerpo if cuerpo else "")
    # El pago de Daniel, si hoy toca o va atrasado: el menú de la mañana es lo
    # primero que ve (2026-11-19). Sin cuenta, sin tablas o con error, nada.
    try:
        from pos_uniformes.services import telegram_mi_pago_service as mp

        linea = mp.aviso(session, hoy)
    except Exception:  # noqa: BLE001
        linea = ""
    if linea:
        texto += "\n\n" + linea
    return texto + "\n\n" + PREGUNTA


def _con_volver(filas=None) -> str:
    return _teclado((filas or []) + [[("‹ Menú", "m:raiz")]])


def es_del_menu(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def atender(dato: str, *, session_factory, hoy: date | None = None) -> tuple[str, str, str]:
    """Un botón del menú: (aviso corto, texto nuevo, botones nuevos).

    El aviso corto es el globito que Telegram enseña arriba; el texto y los
    botones reemplazan el mensaje, para no dejar un reguero en el chat."""
    from pos_uniformes.services import telegram_bot_service as bot
    from pos_uniformes.services import telegram_pagos_service as pg

    accion = str(dato or "")[len(PREFIJO):]

    if accion in ("", "raiz"):
        with session_factory() as session:
            texto, botones = menu_raiz(session, hoy=hoy)
        return "", texto, botones

    if accion == "gente":
        from pos_uniformes.services.telegram_formato import encabezado

        return "", encabezado("👥", "Las muchachas") + "\n¿De las muchachas, qué?", _con_volver(_gente())

    # Pagar a alguien: el desglose primero, el dinero después.
    if accion.startswith("pagar:"):
        code = accion.split(":", 1)[1]
        with session_factory() as session:
            texto = pg.desglose_por_code(session, code, hoy=hoy)
            monto = pg.monto_pendiente(session, code, hoy=hoy)
            hay = pg.tiene_pendiente(session, code, hoy=hoy)
        # El botón lleva el monto que se enseñó: si al tocarlo ya es otro
        # (entraron comisiones), se enseña el nuevo y se pregunta otra vez
        # (auditoría 2026-11-07). Con $0 (el préstamo se lo come) el botón
        # cierra el ciclo.
        etiqueta = "✅ Sí, pagar" if monto > 0 else "✅ Cerrar su ciclo ($0, el préstamo se lo lleva)"
        botones = _con_volver([[(etiqueta, f"{PREFIJO}pagarok:{code}:{monto:.2f}")]] if hay else [])
        return "", texto, botones

    if accion.startswith("pagarok:"):
        code, _, mostrado = accion.split(":", 1)[1].partition(":")
        with session_factory() as session:
            if mostrado:
                ahora_es = pg.monto_pendiente(session, code, hoy=hoy)
                visto = bot.leer_cifra(mostrado)
                if visto is not None and ahora_es > 0 and abs(ahora_es - visto) >= Decimal("0.01"):
                    from pos_uniformes.services.telegram_formato import SALTO

                    texto = pg.desglose_por_code(session, code, hoy=hoy)
                    # Un solo encabezado y una sola cifra 💰: los del desglose
                    # («💵 PAGO A … / 💰 $X a pagar»); el aviso va debajo (2026-11-20).
                    arriba, _, resto = texto.partition(SALTO)
                    aviso_monto = (f"⚠️ El monto cambió desde que lo viste: era ${visto:,.2f} y ahora es "
                                   f"${ahora_es:,.2f}. No pagué nada.")
                    return (
                        "Cambió el monto",
                        SALTO.join(p for p in (arriba, aviso_monto, resto) if p),
                        _con_volver([[("✅ Sí, pagar", f"{PREFIJO}pagarok:{code}:{ahora_es:.2f}")]]),
                    )
            texto = pg.pagar_por_code(session, code, quien=bot.CODIGO_REMOTO, hoy=hoy)
        # El globito decía «Pagado» pasara lo que pasara, también cuando no se
        # pagó nada. Un visto bueno que sale siempre no informa (2026-10-08).
        return ("Pagado" if texto.startswith("✅") else ""), texto, _con_volver()

    if accion == "prestamos":
        from pos_uniformes.services import telegram_prestamos_service as prs

        with session_factory() as session:
            texto, botones = prs.texto_y_botones(session)
        return "", texto, botones

    if accion == "descansos":
        from pos_uniformes.services import telegram_descansos_service as dsc

        with session_factory() as session:
            texto, botones = dsc.texto_y_botones(session, hoy=hoy)
        return "", texto, botones

    if accion == "programas":
        from pos_uniformes.services import telegram_membresias_service as mbs

        with session_factory() as session:
            texto, botones = mbs.texto_y_botones(session)
        return "", texto, botones

    if accion == "vacaciones":
        from pos_uniformes.services import telegram_vacaciones_service as vac
        from pos_uniformes.services import vacaciones_service as vs

        if vs.EN_CONSTRUCCION:
            return "", vs.EN_CONSTRUCCION_TEXTO, ""

        with session_factory() as session:
            texto, botones = vac.texto_y_botones(session)
        return "", texto, botones

    if accion in ("cajon", "cajón"):
        from pos_uniformes.services import telegram_cajon_service as cj

        with session_factory() as session:
            texto, botones = cj.texto_y_botones(session)
        return "", texto, botones

    if accion == "avisos":
        from pos_uniformes.services import telegram_avisos_service as av

        with session_factory() as session:
            texto, botones = av.texto_y_botones(session)
        return "", texto, botones

    if accion == "pagos":
        with session_factory() as session:
            texto = pg.pagos(session, hoy=hoy)
            filas = [
                [(nombre, f"{PREFIJO}pagar:{code}")]
                for code, nombre in pg.quienes_cobran(session, hoy=hoy)
            ]
        return "", texto, _con_volver(filas)

    # Lo demás es de solo mirar: se contesta con el mismo comando de siempre.
    if accion == "cortes":
        from pos_uniformes.services import telegram_cortes_service as ct

        with session_factory() as session:
            texto, botones = ct.texto_y_botones(session)
        return "", texto, botones

    # «hoy» y «pendientes» ya no tienen botón, pero el despachador los sigue
    # atendiendo: los mensajes viejos del chat conservan sus botones, y tocar
    # uno no debe contestar «no conozco ese botón».
    comando = {
        "pulso": "/pulso",
        "hoy": "/hoy",
        "estado": "/estado",
        "resumen": "/resumen",
        "pendientes": "/pendientes",
        "asistencia": "/asistencia",
        "contar": "/contar",
        "faltas": "/faltas",
        "ayuda": "/ayuda",
    }.get(accion)
    if comando is None:
        return "No conozco ese botón", "", ""
    texto = bot.atender_texto(comando, session_factory=session_factory, hoy=hoy)
    return "", texto, _con_volver()
