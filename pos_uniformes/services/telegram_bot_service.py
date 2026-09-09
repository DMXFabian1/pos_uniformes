"""Bot de Telegram para ordenar cosas desde el celular (solo Daniel).

Comandos:
    /corte        hace el corte ahora e imprime el ticket en la tienda
    /nocorte      deja pasar el corte que se propuso hoy
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
    "/nocorte — dejar pasar el corte propuesto hoy\n"
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
    if cmd.nombre == "nocorte":
        from pos_uniformes.services.corte_propuesta_service import cancelar

        if cancelar(hoy):
            return "Ok, hoy no se hace el corte. Cuando quieras, /corte."
        return "No hay ningún corte propuesto hoy. Si lo quieres hacer, /corte."
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


MAX_ANTIGUEDAD_SEG = 10 * 60  # mensajes más viejos (bot apagado) no se ejecutan


def _es_viejo(msg: dict, ahora: float | None = None) -> bool:
    """Un /corte mandado ayer, con el bot apagado, no debe ejecutarse hoy."""
    try:
        fecha = float(msg.get("date") or 0)
    except (TypeError, ValueError):
        return False
    if not fecha:
        return False
    return ((ahora if ahora is not None else time.time()) - fecha) > MAX_ANTIGUEDAD_SEG


ESPERA_GETUPDATES_SEG = 15  # corta para que las alertas de la cola salgan pronto


def escuchar(*, session_factory, token: str, chat_id: str, una_vez: bool = False, alertas: bool = True, on_tick=None) -> None:
    """Long-polling: atiende mensajes del chat autorizado hasta que lo paren.
    En cada vuelta también manda las alertas encoladas (cortes, retiros) y
    lo que vea el vigilante (cierre sin corte, movimientos fuera de horario)."""
    from pos_uniformes.services import telegram_service
    from pos_uniformes.services.alertas_service import Vigilante, procesar

    offset = None
    vigilante = Vigilante() if alertas else None
    logger.info("Bot escuchando (chat %s)…", chat_id)

    def _mandar(texto: str) -> None:
        telegram_service.enviar_mensaje(texto, token=token, chat_id=chat_id)

    while True:
        if on_tick is not None:
            try:
                on_tick()  # latido: el vigía sabe que seguimos vivos
            except Exception:  # noqa: BLE001
                pass
        if alertas:
            procesar(session_factory, _mandar, vigilante)
        try:
            datos = {"timeout": ESPERA_GETUPDATES_SEG}
            if offset is not None:
                datos["offset"] = offset
            payload = telegram_service._llamar(token, "getUpdates", datos, timeout=ESPERA_GETUPDATES_SEG + 15)
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
            if _es_viejo(msg):
                logger.info("Mensaje viejo ignorado: %r", texto)
                respuesta = (
                    f"Ya estoy en línea. No atendí «{texto[:40]}» porque es de antes de arrancar; "
                    "si todavía lo quieres, mándalo otra vez."
                ) if parsear(texto) else ""
                if not respuesta:
                    continue
            else:
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
