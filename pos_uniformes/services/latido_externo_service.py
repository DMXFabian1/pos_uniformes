"""Que alguien de FUERA se dé cuenta cuando la tienda se calla (2026-11-07).

Auditoría del bot, sección 6: «si la PC servidor se apaga, todo queda en
silencio, y eso se ve igual que un día tranquilo». El bot, el vigilante, el
resumen y el corte automático viven en esa PC: si se va la luz, se cae
Windows o se queda sin internet, nadie queda para avisar.

La salida es un «interruptor de hombre muerto» afuera: el bot le manda un
latido cada 5 minutos a un servicio en internet (healthchecks.io, gratis), y
si los latidos dejan de llegar es ESE servicio el que le escribe a Daniel por
Telegram. Así el aviso llega aunque en la tienda no haya ni luz.

Daniel crea el check en healthchecks.io (una vez, desde el celular) y le
pasa la dirección al bot: `/latido https://hc-ping.com/…`. Sin dirección no
se manda nada y /pulso dice que no hay vigilancia desde fuera.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.request

logger = logging.getLogger(__name__)

VARIABLE = "POS_UNIFORMES_LATIDO_URL"
SEGUNDOS_ENTRE_LATIDOS = 5 * 60
_HOSTS_VALIDOS = ("hc-ping.com", "healthchecks.io")

_estado = {"ultimo_intento": 0.0, "ultimo_ok": 0.0, "ultimo_error": ""}
_candado = threading.Lock()


def url_configurada() -> str:
    from pos_uniformes.services.telegram_service import _config

    return _config(VARIABLE)


def es_url_valida(url: str) -> bool:
    from urllib.parse import urlparse

    partes = urlparse((url or "").strip())
    host = (partes.hostname or "").lower()
    return partes.scheme == "https" and any(host == h or host.endswith("." + h) for h in _HOSTS_VALIDOS) \
        and len(partes.path.strip("/")) >= 8


def _mandar(url: str, timeout: float = 10.0) -> None:
    from pos_uniformes.services.telegram_service import _contexto_ssl

    req = urllib.request.Request(url, headers={"User-Agent": "pos-uniformes-latido"})
    with urllib.request.urlopen(req, timeout=timeout, context=_contexto_ssl(True)) as resp:
        resp.read(64)


def latir(ahora: float | None = None, *, en_hilo: bool = True, enviar=None) -> bool:
    """Manda el latido si toca (cada 5 min). Nunca bloquea al bot ni lo tumba.

    Devuelve True si se lanzó un latido en esta llamada."""
    url = url_configurada()
    if not url:
        return False
    ahora = time.time() if ahora is None else ahora
    with _candado:
        if ahora - _estado["ultimo_intento"] < SEGUNDOS_ENTRE_LATIDOS:
            return False
        _estado["ultimo_intento"] = ahora
    enviar = enviar or _mandar

    def _hacer() -> None:
        try:
            enviar(url)
        except Exception as exc:  # noqa: BLE001 — sin línea, el servicio de afuera es el que avisa
            _estado["ultimo_error"] = f"{type(exc).__name__}: {exc}"[:200]
            logger.info("Latido externo no salió: %s", exc)
        else:
            _estado["ultimo_ok"] = time.time()
            _estado["ultimo_error"] = ""

    if en_hilo:
        threading.Thread(target=_hacer, name="latido-externo", daemon=True).start()
    else:
        _hacer()
    return True


def guardar_url(url: str) -> str:
    """`/latido <url>`: la guarda en pos_uniformes.env y manda el primero."""
    import os

    url = (url or "").strip()
    if url.lower() in ("quitar", "no", "apagar"):
        _escribir("")
        os.environ.pop(VARIABLE, None)
        return "Listo: ya no mando latidos afuera. Si la PC se apaga, nadie te va a avisar."
    if not es_url_valida(url):
        return (
            "Esa dirección no es de healthchecks.io. Se ve así:\n"
            "/latido https://hc-ping.com/1234abcd-…\n\n" + instrucciones()
        )
    _escribir(url)
    os.environ[VARIABLE] = url
    _estado["ultimo_intento"] = 0.0
    try:
        _mandar(url)
    except Exception as exc:  # noqa: BLE001
        return (f"La guardé, pero el primer latido no salió ({type(exc).__name__}). "
                "Revisa que la dirección esté completa; lo vuelvo a intentar en 5 minutos.")
    _estado["ultimo_ok"] = time.time()
    return ("✅ Vigilancia desde fuera activa: le mando un latido cada 5 minutos a healthchecks.io.\n"
            "Si dejan de llegar (se fue la luz, se apagó la PC o no hay internet), healthchecks te escribe "
            "por Telegram aunque aquí no quede nadie.")


def _escribir(valor: str) -> None:
    from pos_uniformes.scripts.resumen_diario_telegram import _escribir_env

    _escribir_env(VARIABLE, valor)


def instrucciones() -> str:
    return (
        "Para que alguien de FUERA te avise si la PC servidor se calla:\n"
        "1. Entra a healthchecks.io desde el celular y crea una cuenta (gratis).\n"
        "2. Crea un check: «Period» 5 minutos y «Grace» 15 minutos.\n"
        "3. En Integrations agrega Telegram (te pide escribirle a su bot).\n"
        "4. Copia la dirección del check (https://hc-ping.com/…) y mándamela:\n"
        "   /latido https://hc-ping.com/…\n"
        "Si la PC se apaga de noche a propósito, en el check pon un horario (Cron) con las horas de la tienda."
    )


def texto_estado(ahora: float | None = None) -> str:
    """El renglón de /pulso."""
    ahora = time.time() if ahora is None else ahora
    if not url_configurada():
        return "⚠️ Nadie vigila desde fuera: si esta PC se apaga, no te llega nada → /latido"
    if _estado["ultimo_ok"]:
        minutos = int((ahora - _estado["ultimo_ok"]) // 60)
        if minutos <= 15:
            hace = "hace un momento" if minutos < 1 else f"hace {minutos} min"
            return f"✅ Vigilancia desde fuera: último latido {hace}"
    if _estado["ultimo_error"]:
        return f"⚠️ Vigilancia desde fuera: el latido no está saliendo ({_estado['ultimo_error'][:80]})"
    return "· Vigilancia desde fuera: configurada, esperando el primer latido"
