"""Envío de mensajes por Telegram (bot propio, sin librerías externas).

Configuración en `pos_uniformes.env`:
    POS_UNIFORMES_TELEGRAM_BOT_TOKEN=123456:ABC...   (lo da @BotFather)
    POS_UNIFORMES_TELEGRAM_CHAT_ID=987654321         (tu chat con el bot)

`obtener_chat_ids(token)` ayuda a descubrir el chat id: escribe cualquier
cosa al bot desde tu Telegram y luego llama esta función.
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request

_API = "https://api.telegram.org/bot{token}/{metodo}"
_API_ARCHIVO = "https://api.telegram.org/file/bot{token}/{ruta}"
_MAX = 4000  # Telegram corta en 4096
_log = logging.getLogger("telegram")
_aviso_inseguro = False


def _contexto_ssl(verificar: bool = True) -> ssl.SSLContext:
    """Contexto TLS que confía en los certificados de Windows.

    En la PC de la tienda el antivirus inspecciona HTTPS con su propio
    certificado; el paquete `truststore` hace que Python use el almacén del
    sistema (donde ese certificado sí está). Sin truststore, el default.
    """
    if not verificar:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    try:
        import truststore  # type: ignore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def _config(nombre: str) -> str:
    valor = os.getenv(nombre)
    if valor is None:
        from pos_uniformes.utils.config import load_runtime_env_overrides

        valor = load_runtime_env_overrides().get(nombre, "")
    return (valor or "").strip()


def token_configurado() -> str:
    return _config("POS_UNIFORMES_TELEGRAM_BOT_TOKEN")


def chat_id_configurado() -> str:
    return _config("POS_UNIFORMES_TELEGRAM_CHAT_ID")


#: Conexión reutilizada contra api.telegram.org. Abrir una nueva en cada
#: llamada cuesta un saludo TLS completo: medido desde la Mac son 571 ms por
#: llamada contra 182 ms reutilizando —un 68% — y en la red de la tienda, que
#: va por WiFi y pierde paquetes, la diferencia es mayor todavía. Como el bot
#: hace una llamada por cada cosa que contesta, eso se siente en el chat.
_pool = None
_pool_verifica: bool | None = None


def _obtener_pool(verificar: bool):
    """PoolManager con NUESTRO contexto TLS (el que confía en el antivirus)."""
    global _pool, _pool_verifica
    if _pool is None or _pool_verifica != verificar:
        import urllib3

        _pool = urllib3.PoolManager(
            ssl_context=_contexto_ssl(verificar), maxsize=4, retries=False
        )
        _pool_verifica = verificar
    return _pool


def soltar_pool() -> None:
    """Olvida la conexión guardada. Para pruebas y para forzar un saludo nuevo."""
    global _pool, _pool_verifica
    _pool, _pool_verifica = None, None


def _pedir(url: str, cuerpo: bytes | None, timeout: float, verificar: bool) -> str:
    """Una llamada HTTP reutilizando la conexión. Cae a urllib si algo raro pasa.

    La red de seguridad importa: este es el único camino por el que habla el
    bot, y romperlo sería dejar a Daniel sin bot estando de viaje. Si el camino
    rápido falla por cualquier motivo que no sea el certificado, se hace la
    llamada como siempre y nadie se entera.
    """
    try:
        import urllib3

        pool = _obtener_pool(verificar)
        if cuerpo is None:
            resp = pool.request("GET", url, timeout=urllib3.Timeout(total=timeout))
        else:
            resp = pool.request(
                "POST", url, body=cuerpo, timeout=urllib3.Timeout(total=timeout),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        return resp.data.decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        if _es_de_certificado(exc):
            raise  # lo atiende quien llama, para caer al modo sin verificar
        _log.debug("Conexión reutilizada falló (%s); se va por el camino de siempre", exc)
        soltar_pool()
        req = urllib.request.Request(url, data=cuerpo)
        with urllib.request.urlopen(req, timeout=timeout, context=_contexto_ssl(verificar)) as resp:
            return resp.read().decode("utf-8")


def _es_de_certificado(exc: BaseException) -> bool:
    """¿El error es el del certificado que no reconoce (antivirus/proxy)?

    Hay que mirar por tres lados porque cada capa lo envuelve a su manera:
    `urlopen` lo guarda en `.reason` (no en la cadena de excepciones), urllib3
    lo encadena con `__cause__`, y a veces solo queda el texto. Perderlo
    significa no reintentar sin verificar, y eso es el bot mudo en la tienda.

    **No se sigue `__context__`**, y es a propósito: `__context__` es «qué se
    estaba atendiendo cuando esto se lanzó», no «qué lo causó». Siguiéndolo,
    un error cualquiera levantado dentro del `except` del error de certificado
    heredaba su causa y se daba por certificado también — con eso el reintento
    sin verificar se quedaba dando vueltas. Lo encontró un test que ya existía.
    """
    visto: set[int] = set()
    pendientes = [exc]
    while pendientes:
        actual = pendientes.pop()
        if actual is None or id(actual) in visto:
            continue
        visto.add(id(actual))
        if isinstance(actual, ssl.SSLCertVerificationError):
            return True
        if "CERTIFICATE_VERIFY_FAILED" in str(actual):
            return True
        pendientes.extend(
            x for x in (actual.__cause__, getattr(actual, "reason", None))
            if isinstance(x, BaseException)
        )
    return False


def _llamar(token: str, metodo: str, datos: dict | None = None, timeout: float = 15.0) -> dict:
    global _aviso_inseguro
    url = _API.format(token=token, metodo=metodo)
    cuerpo = urllib.parse.urlencode(datos or {}).encode("utf-8")

    def _abrir(verificar: bool):
        return json.loads(_pedir(url, cuerpo if datos else None, timeout, verificar))

    try:
        payload = _abrir(True)
    except Exception as exc:  # noqa: BLE001
        # urlopen envuelve el error TLS en URLError(reason=…); urllib3 lo
        # envuelve distinto. `_es_de_certificado` mira toda la cadena.
        if not _es_de_certificado(exc):
            raise
        # Último recurso: el antivirus intercepta y su certificado no está
        # en el almacén que ve Python. Se avisa una vez y se sigue.
        if not _aviso_inseguro:
            _aviso_inseguro = True
            msg = "Telegram: certificado no reconocido (antivirus/proxy); continuando sin verificar TLS."
            _log.warning(msg)
            print(msg)
        soltar_pool()
        payload = _abrir(False)
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram respondió: {payload.get('description', payload)}")
    return payload


#: Tope de lo que se baja de Telegram. Una foto de celular no pasa de aquí, y
#: pone un techo a lo que un mensaje puede hacer descargar al bot.
MAX_ARCHIVO_BYTES = 10 * 1024 * 1024


def bajar_archivo(file_id: str, *, token: str | None = None, timeout: float = 30.0) -> bytes:
    """Baja un archivo del bot por su `file_id` (dos pasos: getFile + descarga).

    Lanza RuntimeError si Telegram no lo da o si pesa más de `MAX_ARCHIVO_BYTES`.
    """
    token = token or token_configurado()
    if not token:
        raise RuntimeError("Falta el token del bot.")
    info = _llamar(token, "getFile", {"file_id": str(file_id)}, timeout=timeout)
    ruta = ((info.get("result") or {}).get("file_path") or "").strip()
    if not ruta:
        raise RuntimeError("Telegram no dio la ruta del archivo.")
    tamano = (info.get("result") or {}).get("file_size") or 0
    if int(tamano or 0) > MAX_ARCHIVO_BYTES:
        raise RuntimeError(f"El archivo pesa {int(tamano) // 1024} KB; es demasiado.")
    url = _API_ARCHIVO.format(token=token, ruta=urllib.parse.quote(ruta))

    def _abrir(verificar: bool) -> bytes:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout, context=_contexto_ssl(verificar)) as resp:
            # +1 para notar el caso de que venga justo en el tope y siga habiendo más.
            datos = resp.read(MAX_ARCHIVO_BYTES + 1)
        if len(datos) > MAX_ARCHIVO_BYTES:
            raise RuntimeError("El archivo es demasiado grande.")
        return datos

    try:
        return _abrir(True)
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as exc:
        razon = getattr(exc, "reason", exc)
        if not isinstance(razon, ssl.SSLCertVerificationError):
            raise
        return _abrir(False)


def foto_mas_grande(msg: dict) -> str | None:
    """`file_id` de la versión más grande de una foto, o None si no hay foto.

    Telegram manda la misma foto en varios tamaños; la última es la mayor.
    También atiende la foto mandada «como archivo» (document con mime de imagen).
    """
    fotos = msg.get("photo") or []
    if fotos:
        mejor = max(fotos, key=lambda f: int(f.get("file_size") or 0))
        return mejor.get("file_id") or None
    doc = msg.get("document") or {}
    if str(doc.get("mime_type") or "").startswith("image/"):
        return doc.get("file_id") or None
    return None


def partir_mensaje(texto: str, maximo: int = _MAX) -> list[str]:
    """Telegram acepta 4096 caracteres por mensaje; se parte por líneas."""
    if len(texto) <= maximo:
        return [texto]
    partes: list[str] = []
    actual = ""
    for linea in texto.split("\n"):
        candidato = f"{actual}\n{linea}" if actual else linea
        if len(candidato) > maximo and actual:
            partes.append(actual)
            actual = linea
        else:
            actual = candidato
    if actual:
        partes.append(actual)
    return partes


def _credenciales(token: str | None, chat_id: str | None) -> tuple[str, str]:
    token = token or token_configurado()
    chat_id = chat_id or chat_id_configurado()
    if not token or not chat_id:
        raise RuntimeError(
            "Falta POS_UNIFORMES_TELEGRAM_BOT_TOKEN o POS_UNIFORMES_TELEGRAM_CHAT_ID en pos_uniformes.env."
        )
    return token, chat_id


def teclado(filas: list[list[tuple[str, str]]]) -> str:
    """Botones debajo del mensaje: [[(texto, dato), …], …] → JSON para Telegram.

    El `dato` regresa tal cual cuando alguien toca (callback_query). Máximo 64
    bytes por botón, por regla de Telegram.
    """
    return json.dumps({
        "inline_keyboard": [
            [{"text": texto, "callback_data": dato[:64]} for texto, dato in fila] for fila in filas
        ]
    })


def enviar_mensaje(
    texto: str, *, token: str | None = None, chat_id: str | None = None, botones: str | None = None
) -> int:
    """Manda el texto (partido si es largo). Devuelve cuántos mensajes salieron.

    `botones`: lo que devuelve `teclado()`; van en el último pedazo."""
    token, chat_id = _credenciales(token, chat_id)
    enviados = 0
    partes = partir_mensaje(texto)
    for i, parte in enumerate(partes):
        datos = {"chat_id": chat_id, "text": parte, "disable_web_page_preview": "true"}
        if botones and i == len(partes) - 1:
            datos["reply_markup"] = botones
        respuesta = _llamar(token, "sendMessage", datos)
        # Se anota AQUÍ y no en cada sitio que manda un aviso: este es el único
        # camino por el que sale un mensaje, así que no hay forma de agregar
        # uno nuevo y que se quede sin barrer (2026-10-08).
        _anotar_para_barrer(respuesta)
        enviados += 1
    return enviados


def _anotar_para_barrer(respuesta: dict) -> None:
    """Apunta el mensaje recién mandado para que el barrido lo borre mañana."""
    try:
        mid = int(((respuesta or {}).get("result") or {}).get("message_id") or 0)
        if mid:
            from pos_uniformes.services import telegram_limpieza_service as limpieza

            limpieza.anotar(mid)
    except Exception:  # noqa: BLE001 — no poder apuntarlo no impide mandarlo
        pass


def borrar_mensaje(message_id: int, *, token: str | None = None, chat_id: str | None = None) -> bool:
    """Borra un mensaje del bot. False si Telegram no deja (pasó de 48 h)."""
    token, chat_id = _credenciales(token, chat_id)
    try:
        _llamar(token, "deleteMessage",
                {"chat_id": chat_id, "message_id": str(int(message_id))})
        return True
    except Exception:  # noqa: BLE001 — ya borrado, o muy viejo
        return False


def fijar_mensaje(message_id: int, *, token: str | None = None, chat_id: str | None = None) -> bool:
    """Fija un mensaje arriba del chat, sin avisar con una notificación."""
    token, chat_id = _credenciales(token, chat_id)
    try:
        _llamar(token, "pinChatMessage", {
            "chat_id": chat_id,
            "message_id": str(int(message_id)),
            "disable_notification": "true",
        })
        return True
    except Exception:  # noqa: BLE001 — sin fijar, el menú sigue sirviendo
        return False


def editar_mensaje(
    message_id: int, texto: str, *, token: str | None = None, chat_id: str | None = None, botones: str | None = None
) -> None:
    """Reescribe un mensaje ya mandado (y sus botones). Para que la lista de
    asistencia se actualice en el mismo lugar en vez de mandar otra."""
    token, chat_id = _credenciales(token, chat_id)
    datos = {"chat_id": chat_id, "message_id": str(message_id), "text": texto[:_MAX]}
    if botones:
        datos["reply_markup"] = botones
    _llamar(token, "editMessageText", datos)


def responder_toque(callback_query_id: str, texto: str = "", *, token: str | None = None) -> None:
    """Le dice a Telegram que el toque se atendió (si no, el botón se queda
    'cargando' en el celular)."""
    token = token or token_configurado()
    datos = {"callback_query_id": callback_query_id}
    if texto:
        datos["text"] = texto[:200]
    _llamar(token, "answerCallbackQuery", datos)


def obtener_chat_ids(token: str | None = None) -> list[tuple[str, str]]:
    """(chat_id, nombre) de quienes le han escrito al bot recientemente."""
    token = token or token_configurado()
    if not token:
        raise RuntimeError("Falta POS_UNIFORMES_TELEGRAM_BOT_TOKEN.")
    payload = _llamar(token, "getUpdates")
    vistos: dict[str, str] = {}
    for upd in payload.get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if "id" in chat:
            nombre = chat.get("title") or " ".join(
                p for p in (chat.get("first_name"), chat.get("last_name")) if p
            ) or chat.get("username") or ""
            vistos[str(chat["id"])] = nombre
    return list(vistos.items())
