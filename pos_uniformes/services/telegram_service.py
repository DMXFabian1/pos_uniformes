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


def _llamar(token: str, metodo: str, datos: dict | None = None, timeout: float = 15.0) -> dict:
    global _aviso_inseguro
    url = _API.format(token=token, metodo=metodo)
    cuerpo = urllib.parse.urlencode(datos or {}).encode("utf-8")

    def _abrir(verificar: bool):
        req = urllib.request.Request(url, data=cuerpo if datos else None)
        with urllib.request.urlopen(req, timeout=timeout, context=_contexto_ssl(verificar)) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        payload = _abrir(True)
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as exc:
        # urlopen envuelve el error TLS en URLError(reason=SSLCertVerificationError).
        razon = getattr(exc, "reason", exc)
        if not isinstance(razon, ssl.SSLCertVerificationError):
            raise
        # Último recurso: el antivirus intercepta y su certificado no está
        # en el almacén que ve Python. Se avisa una vez y se sigue.
        if not _aviso_inseguro:
            _aviso_inseguro = True
            msg = "Telegram: certificado no reconocido (antivirus/proxy); continuando sin verificar TLS."
            _log.warning(msg)
            print(msg)
        payload = _abrir(False)
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram respondió: {payload.get('description', payload)}")
    return payload


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


def enviar_mensaje(texto: str, *, token: str | None = None, chat_id: str | None = None) -> int:
    """Manda el texto (partido si es largo). Devuelve cuántos mensajes salieron."""
    token = token or token_configurado()
    chat_id = chat_id or chat_id_configurado()
    if not token or not chat_id:
        raise RuntimeError(
            "Falta POS_UNIFORMES_TELEGRAM_BOT_TOKEN o POS_UNIFORMES_TELEGRAM_CHAT_ID en pos_uniformes.env."
        )
    enviados = 0
    for parte in partir_mensaje(texto):
        _llamar(token, "sendMessage", {"chat_id": chat_id, "text": parte, "disable_web_page_preview": "true"})
        enviados += 1
    return enviados


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
