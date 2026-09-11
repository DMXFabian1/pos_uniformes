"""Impedir que la computadora se suspenda mientras el bot recolecta.

Un equipo que se duerme deja huecos en los datos y pierde los partidos que arrancan
entretanto. En Windows se usa SetThreadExecutionState; en macOS, `caffeinate`. En Linux
(servidores) no hace falta y es un no-op. Nunca lanza excepción: si no se puede, avisa y sigue.
"""
from __future__ import annotations

import logging
import subprocess
import sys

log = logging.getLogger(__name__)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


class KeepAwake:
    """Context manager. `active` dice si realmente se logró bloquear la suspensión."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.active = False
        self._proc: subprocess.Popen | None = None

    def __enter__(self) -> "KeepAwake":
        if not self.enabled:
            return self
        try:
            if sys.platform == "win32":
                import ctypes

                if ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED):
                    self.active = True
                    log.info("suspensión bloqueada mientras el bot corre (la pantalla sí puede apagarse)")
            elif sys.platform == "darwin":
                self._proc = subprocess.Popen(["caffeinate", "-i"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.active = True
                log.info("suspensión bloqueada con caffeinate mientras el bot corre")
        except Exception as e:  # noqa: BLE001
            log.warning("no se pudo bloquear la suspensión (%s); revisa las opciones de energía", e)
        return self

    def __exit__(self, *exc: object) -> None:
        if not self.active:
            return
        try:
            if sys.platform == "win32":
                import ctypes

                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            elif self._proc is not None:
                self._proc.terminate()
        except Exception:  # noqa: BLE001
            pass
        self.active = False
