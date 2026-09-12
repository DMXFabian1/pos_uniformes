"""Bot de Telegram para ordenar cosas desde el celular (solo Daniel).

Comandos:
    /corte        hace el corte ahora e imprime el ticket en la tienda
    /corte 5000   igual, pero se retiran $5,000 (el ticket cuadra con eso)
    /corte sintarjeta   igual, pero los cobros con tarjeta quedan ocultos
    /nocorte      deja pasar el corte que se propuso hoy
    /estado       qué hay en caja ahora mismo
    /resumen      el resumen del día (el mismo de la noche)
    /pendientes   lo que falta por registrar
    /asistencia   quién vino hoy (deducido de su primer movimiento)
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
from decimal import Decimal, InvalidOperation

logger = logging.getLogger("telegram_bot")

CODIGO_REMOTO = "VEND-1"  # Daniel: el que manda /corte

AYUDA = (
    "Comandos:\n"
    "/corte — hacer el corte ahora e imprimir el ticket en la tienda\n"
    "/corte 5000 — el mismo corte, pero se retiran $5,000\n"
    "/corte sintarjeta — sin que se vean los cobros con tarjeta\n"
    "   (se pueden juntar: /corte 5000 sintarjeta)\n"
    "/nocorte — dejar pasar el corte propuesto hoy\n"
    "/estado — qué hay en caja ahora\n"
    "/resumen — resumen del día\n"
    "/pendientes — lo que falta por registrar\n"
    "/asistencia — quién vino hoy, con un comando por empleada para marcar\n"
    "/falta_Fanny · /descanso_Fanny · /vino_Fanny — o con espacio: /falta Fanny\n"
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
    argumento = partes[1].strip() if len(partes) > 1 else ""
    # "/falta_Fanny" (tocable en Telegram, una sola palabra) = "/falta Fanny".
    for base in ("falta", "descanso", "vino"):
        if nombre.startswith(base + "_") and len(nombre) > len(base) + 1:
            return Comando(base, (partes[0].split("@")[0][len(base) + 1:] + " " + argumento).strip())
    return Comando(nombre, argumento)


@dataclass(frozen=True)
class OpcionesCorte:
    """Lo que trae `/corte`: cuánto se retira y si se esconde la tarjeta."""

    retirar: Decimal | None = None
    sin_tarjeta: bool = False


_SIN_TARJETA = {"sintarjeta", "sin-tarjeta", "sin_tarjeta", "st"}


def leer_opciones_corte(argumento: str) -> OpcionesCorte:
    """'5000 sintarjeta' → retira $5,000 y esconde la tarjeta. En cualquier
    orden; '$5,000.50' también vale."""
    retirar: Decimal | None = None
    sin_tarjeta = False
    for palabra in (argumento or "").split():
        limpia = palabra.strip().lower()
        if limpia in _SIN_TARJETA:
            sin_tarjeta = True
            continue
        crudo = limpia.replace("$", "").replace(",", "").replace("_", "")
        try:
            valor = Decimal(crudo)
        except (InvalidOperation, ValueError):
            raise ValueError(
                f"No entendí «{palabra}». Se usa así:\n"
                "/corte — con la cifra calculada\n"
                "/corte 5000 — se retiran $5,000\n"
                "/corte 5000 sintarjeta — además, sin los cobros con tarjeta"
            ) from None
        if valor < 0:
            raise ValueError("Lo que se retira no puede ser negativo.")
        retirar = valor.quantize(Decimal("0.01"))
    return OpcionesCorte(retirar=retirar, sin_tarjeta=sin_tarjeta)


def atender_texto(texto: str, *, session_factory, hoy: date | None = None) -> str:
    """Devuelve la respuesta para un mensaje. `session_factory()` abre sesión."""
    cmd = parsear(texto)
    if cmd is None:
        return "No entendí. " + AYUDA
    if cmd.nombre in ("ayuda", "help", "start"):
        return AYUDA
    if cmd.nombre == "corte":
        from pos_uniformes.services.corte_remoto_service import hacer_corte_y_avisar

        try:
            opciones = leer_opciones_corte(cmd.argumento)
        except ValueError as exc:
            return str(exc)
        with session_factory() as session:
            return hacer_corte_y_avisar(
                session, creado_por=CODIGO_REMOTO,
                retirar=opciones.retirar, sin_tarjeta=opciones.sin_tarjeta,
            ).mensaje
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
    if cmd.nombre == "asistencia":
        with session_factory() as session:
            return mensaje_asistencia(session, hoy)[0]
    if cmd.nombre in ("vino", "falta", "descanso"):
        from pos_uniformes.services import asistencia_service as asis

        accion = {"vino": asis.VINO, "falta": asis.NO_VINO, "descanso": asis.DESCANSA}[cmd.nombre]
        with session_factory() as session:
            code = asis.buscar_code(session, cmd.argumento)
            if code is None:
                return f"¿Quién? Escribe el nombre como aparece en la lista: /{cmd.nombre} Fanny"
            hecho = asis.marcar(session, code, accion, hoy)
            return hecho + "\n\n" + mensaje_asistencia(session, hoy)[0]
    return f"No conozco /{cmd.nombre}. " + AYUDA


def mensaje_asistencia(session, hoy: date | None = None) -> tuple[str, str]:
    """(texto, botones JSON) de la lista de asistencia de hoy.

    Los botones quedaron en desuso (Daniel prefiere los comandos tocables
    que van en el propio texto: /falta_Fanny, /descanso_Fanny); se devuelve
    "" para no mandarlos. La infraestructura de toques sigue viva por si
    vuelve a hacer falta."""
    from pos_uniformes.services import asistencia_service as asis

    lista = asis.asistencia_del_dia(session, hoy)
    return asis.texto_asistencia(lista, hoy), ""


def atender_toque(dato: str, *, session_factory, hoy: date | None = None) -> tuple[str, str, str] | None:
    """Un botón de asistencia tocado: marca y devuelve (aviso corto, texto nuevo, botones nuevos).
    None si el dato no es de asistencia."""
    from pos_uniformes.services import asistencia_service as asis

    toque = asis.interpretar_toque(dato)
    if toque is None:
        return None
    code, accion = toque
    with session_factory() as session:
        aviso = asis.marcar(session, code, accion, hoy)
        texto, botones = mensaje_asistencia(session, hoy)
    return aviso, texto, botones


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


ESPERA_GETUPDATES_SEG = 25  # una vuelta cada ~25 s: alertas casi al momento y pocas consultas


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
            toque = upd.get("callback_query")
            if toque:
                _atender_toque(toque, session_factory=session_factory, token=token, chat_id=chat_id)
                continue
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


def _atender_toque(toque: dict, *, session_factory, token: str, chat_id: str) -> None:
    """Un botón tocado en el celular: marca, avisa y reescribe la lista en el
    mismo mensaje. Solo del chat autorizado."""
    from pos_uniformes.services import telegram_service

    msg = toque.get("message") or {}
    chat = str((msg.get("chat") or {}).get("id", ""))
    if chat != str(chat_id):
        logger.info("Toque ignorado de chat %s", chat)
        return
    dato = str(toque.get("data") or "")
    try:
        resultado = atender_toque(dato, session_factory=session_factory)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error atendiendo el toque %r", dato)
        resultado = (f"Falló: {exc}", "", "")
    try:
        telegram_service.responder_toque(str(toque.get("id", "")), resultado[0] if resultado else "", token=token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo responder el toque: %s", exc)
    if resultado and resultado[1] and msg.get("message_id") is not None:
        try:
            telegram_service.editar_mensaje(
                int(msg["message_id"]), resultado[1], token=token, chat_id=chat_id, botones=resultado[2]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo actualizar la lista: %s", exc)
