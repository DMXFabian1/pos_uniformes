"""El menú del bot: tocar en vez de recordar.

Son 19 comandos y Daniel pidió la chuleta justamente porque se le olvidan
(2026-09-25). El menú los pone a un toque, y el mensaje se reescribe en su
lugar en vez de llenar el chat: se entra, se ve, se vuelve.

Lo que mueve dinero **no** queda a un toque: pagar pide el segundo toque sobre
el desglose, igual que por texto pide la palabra de más. El corte y el retiro
no están aquí a propósito — llevan cantidad y motivo, y eso se escribe.
"""

from __future__ import annotations

from datetime import date

#: Prefijo de los datos que viajan en los botones (máx. 64 bytes por regla de Telegram).
PREFIJO = "m:"

_RAIZ = [
    [("📅 Hoy", "m:hoy"), ("💵 Caja", "m:estado")],
    [("📋 Resumen", "m:resumen"), ("⏳ Pendientes", "m:pendientes")],
    [("💰 Pagos", "m:pagos"), ("👥 Quién vino", "m:asistencia")],
    [("🏪 Qué contar", "m:contar"), ("🔎 Sin surtir", "m:faltas")],
    [("❔ Ayuda", "m:ayuda")],
]


def _teclado(filas):
    from pos_uniformes.services import telegram_service

    return telegram_service.teclado(filas)


def menu_raiz() -> tuple[str, str]:
    """(texto, botones) del menú principal."""
    return "¿Qué quieres ver?", _teclado(_RAIZ)


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
        texto, botones = menu_raiz()
        return "", texto, botones

    # Pagar a alguien: el desglose primero, el dinero después.
    if accion.startswith("pagar:"):
        code = accion.split(":", 1)[1]
        with session_factory() as session:
            texto = pg.desglose_por_code(session, code, hoy=hoy)
            puede = pg.tiene_pendiente(session, code, hoy=hoy)
        botones = _con_volver([[("✅ Sí, pagar", f"{PREFIJO}pagarok:{code}")]] if puede else [])
        return "", texto, botones

    if accion.startswith("pagarok:"):
        code = accion.split(":", 1)[1]
        with session_factory() as session:
            texto = pg.pagar_por_code(session, code, quien=bot.CODIGO_REMOTO, hoy=hoy)
        return "Pagado", texto, _con_volver()

    if accion == "pagos":
        with session_factory() as session:
            texto = pg.pagos(session, hoy=hoy)
            filas = [
                [(nombre, f"{PREFIJO}pagar:{code}")]
                for code, nombre in pg.quienes_cobran(session, hoy=hoy)
            ]
        return "", texto, _con_volver(filas)

    # Lo demás es de solo mirar: se contesta con el mismo comando de siempre.
    comando = {
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
