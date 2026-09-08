"""Envío de mensajes por Telegram (bot propio, sin librerías externas).

Configuración en `pos_uniformes.env`:
    POS_UNIFORMES_TELEGRAM_BOT_TOKEN=123456:ABC...   (lo da @BotFather)
    POS_UNIFORMES_TELEGRAM_CHAT_ID=987654321         (tu chat con el bot)

`obtener_chat_ids(token)` ayuda a descubrir el chat id: escribe cualquier
cosa al bot desde tu Telegram y luego llama esta función.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

_API = "https://api.telegram.org/bot{token}/{metodo}"
_MAX = 4000  # Telegram corta en 4096


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
    url = _API.format(token=token, metodo=metodo)
    cuerpo = urllib.parse.urlencode(datos or {}).encode("utf-8")
    req = urllib.request.Request(url, data=cuerpo if datos else None)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
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
