"""Escucha el bot de Telegram en la PC servidor.

    python -m pos_uniformes.scripts.telegram_bot

Lo levanta `telegram_bot_vigia.py` (tarea cada 5 min y al iniciar sesión),
sin ventana. Aquí:
- candado (mutex de Windows): si ya hay un bot corriendo, este sale;
  dos bots pelean por getUpdates (409) y "funciona de a ratos";
- latido en `data/telegram_bot.heartbeat` cada vuelta: si se queda pegado,
  el vigía lo mata y lo vuelve a levantar;
- log en `logs/telegram_bot.log` (no depende de una consola abierta).
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

NOMBRE_MUTEX = "Global\\POSUniformesTelegramBot"
MAX_SEG_SIN_LATIDO = 180


def _base() -> Path:
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir()


def ruta_latido() -> Path:
    return _base() / "data" / "telegram_bot.heartbeat"


def ruta_pid() -> Path:
    return _base() / "data" / "telegram_bot.pid"


def ruta_log() -> Path:
    return _base() / "logs" / "telegram_bot.log"


def latir() -> None:
    p = ruta_latido()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(time.time()), encoding="utf-8")


def latido_fresco(ahora: float | None = None, max_seg: int = MAX_SEG_SIN_LATIDO) -> bool:
    """True si el bot dio señales de vida hace menos de `max_seg`."""
    try:
        ultimo = float(ruta_latido().read_text(encoding="utf-8").strip())
    except Exception:  # noqa: BLE001
        return False
    return ((ahora if ahora is not None else time.time()) - ultimo) < max_seg


def tomar_candado() -> bool:
    """Un solo bot por máquina. En Windows usa un mutex con nombre; en otros
    sistemas (Mac de desarrollo) no bloquea."""
    if not sys.platform.startswith("win"):
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.CreateMutexW(None, True, NOMBRE_MUTEX)
    if not handle:
        return True
    ya_existia = kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    if ya_existia:
        return False
    global _MUTEX
    _MUTEX = handle  # se libera al morir el proceso
    return True


_MUTEX = None


def _configurar_log() -> None:
    from logging.handlers import RotatingFileHandler

    ruta = ruta_log()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%d/%m %H:%M:%S")
    archivo = RotatingFileHandler(ruta, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    archivo.setFormatter(fmt)
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(archivo)
    if sys.stdout is not None and sys.stdout.isatty():
        consola = logging.StreamHandler()
        consola.setFormatter(fmt)
        raiz.addHandler(consola)


def main() -> int:
    _configurar_log()
    log = logging.getLogger("telegram_bot")
    if not tomar_candado():
        log.info("Ya hay un bot corriendo en esta PC; este sale.")
        return 0
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services import telegram_service
    from pos_uniformes.services.telegram_bot_service import escuchar

    token = telegram_service.token_configurado()
    chat_id = telegram_service.chat_id_configurado()
    if not token or not chat_id:
        log.error("Falta POS_UNIFORMES_TELEGRAM_BOT_TOKEN o POS_UNIFORMES_TELEGRAM_CHAT_ID en pos_uniformes.env.")
        return 1
    try:
        ruta_pid().parent.mkdir(parents=True, exist_ok=True)
        ruta_pid().write_text(str(os.getpid()), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    latir()
    log.info("Bot arrancando (pid %s)", os.getpid())
    while True:
        try:
            escuchar(session_factory=get_session, token=token, chat_id=chat_id, on_tick=latir)
        except KeyboardInterrupt:
            return 0
        except Exception:  # noqa: BLE001 — nunca morir: esperar y volver
            log.exception("El bot tronó; reintento en 15 s")
            time.sleep(15)


if __name__ == "__main__":
    sys.exit(main())
