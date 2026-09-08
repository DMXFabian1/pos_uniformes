"""Bot de Telegram para ordenar cosas desde el celular (solo Daniel).

Comandos:
    /corte        hace el corte ahora e imprime el ticket en la tienda
    /estado       qué hay en caja ahora mismo
    /resumen      el resumen del día (el mismo de la noche)
    /pendientes   lo que falta por registrar
    /ayuda        esta lista

Solo responde al chat configurado (POS_UNIFORMES_TELEGRAM_CHAT_ID); a
cualquier otro lo ignora. `atender_texto` es la lógica (testeable); el
`escuchar` hace long-polling contra la API.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger("telegram_bot")

CODIGO_REMOTO = "VEND-1"  # Daniel: el que manda /corte

AYUDA = (
    "Comandos:\n"
    "/corte — hacer el corte ahora e imprimir el ticket en la tienda\n"
    "/estado — qué hay en caja ahora\n"
    "/resumen — resumen del día\n"
    "/pendientes — lo que falta por registrar\n"
    "/ayuda — esta lista"
)


@dataclass(frozen=True)
class Comando:
    nombre: str
    argumento: str = ""


def parsear(texto: str) -> Comando | None:
    t = (texto or "").strip()
    if not t.startswith("/"):
        return None
    partes = t[1:].split(maxsplit=1)
    nombre = partes[0].split("@")[0].lower()
    return Comando(nombre, partes[1].strip() if len(partes) > 1 else "")


def atender_texto(texto: str, *, session_factory, hoy: date | None = None) -> str:
    """Devuelve la respuesta para un mensaje. `session_factory()` abre sesión."""
    cmd = parsear(texto)
    if cmd is None:
        return "No entendí. " + AYUDA
    if cmd.nombre in ("ayuda", "help", "start"):
        return AYUDA
    if cmd.nombre == "corte":
        from pos_uniformes.services.corte_remoto_service import hacer_corte_y_avisar

        with session_factory() as session:
            return hacer_corte_y_avisar(session, creado_por=CODIGO_REMOTO).mensaje
    if cmd.nombre == "estado":
        from pos_uniformes.services.corte_remoto_service import texto_estado_actual

        with session_factory() as session:
            return texto_estado_actual(session)
    if cmd.nombre == "resumen":
        from pos_uniformes.services.resumen_diario_service import formatear, recolectar

        with session_factory() as session:
            return formatear(recolectar(session, hoy))
    if cmd.nombre == "pendientes":
        from pos_uniformes.services.resumen_diario_service import texto_solo_pendientes

        with session_factory() as session:
            return texto_solo_pendientes(session, hoy) or "Sin pendientes. ✅"
    return f"No conozco /{cmd.nombre}. " + AYUDA


def escuchar(*, session_factory, token: str, chat_id: str, una_vez: bool = False) -> None:
    """Long-polling: atiende mensajes del chat autorizado hasta que lo paren."""
    from pos_uniformes.services import telegram_service

    offset = None
    logger.info("Bot escuchando (chat %s)…", chat_id)
    while True:
        try:
            datos = {"timeout": 30}
            if offset is not None:
                datos["offset"] = offset
            payload = telegram_service._llamar(token, "getUpdates", datos, timeout=45)
        except Exception as exc:  # noqa: BLE001
            logger.warning("getUpdates falló: %s", exc)
            time.sleep(10)
            if una_vez:
                return
            continue
        for upd in payload.get("result", []):
            offset = int(upd["update_id"]) + 1
            msg = upd.get("message") or {}
            chat = str((msg.get("chat") or {}).get("id", ""))
            texto = msg.get("text") or ""
            if chat != str(chat_id):
                logger.info("Mensaje ignorado de chat %s", chat)
                continue
            try:
                respuesta = atender_texto(texto, session_factory=session_factory)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Error atendiendo %r", texto)
                respuesta = f"Falló: {exc}"
            try:
                telegram_service.enviar_mensaje(respuesta, token=token, chat_id=chat_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo responder: %s", exc)
        if una_vez:
            return
