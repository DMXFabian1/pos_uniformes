"""Vigía del bot de Telegram (PC servidor).

    python -m pos_uniformes.scripts.telegram_bot_vigia [--reiniciar]

Lo corre una tarea de Windows cada 5 min y al iniciar sesión:
- si el bot late (heartbeat < 3 min) no hace nada;
- si no late (no está, se colgó, cerraron la ventana), lo levanta SIN
  ventana; si había un proceso pegado, lo mata primero;
- `--reiniciar` fuerza matar y levantar (lo usa la actualización para que
  el bot tome el código nuevo).
Sin token configurado no hace nada.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time


def decidir(*, fresco: bool, reiniciar: bool) -> str:
    """'nada' | 'levantar' | 'reiniciar' (puro, testeable)."""
    if reiniciar:
        return "reiniciar"
    return "nada" if fresco else "levantar"


def _pid_guardado() -> int | None:
    from pos_uniformes.scripts.telegram_bot import ruta_pid

    try:
        return int(ruta_pid().read_text(encoding="utf-8").strip())
    except Exception:  # noqa: BLE001
        return None


def matar(pid: int | None) -> None:
    if not pid or pid == os.getpid():
        return
    try:
        if sys.platform.startswith("win"):
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=20)
        else:
            os.kill(pid, 9)
    except Exception:  # noqa: BLE001
        pass


def levantar() -> int:
    """Arranca el bot en segundo plano, sin consola. Devuelve el pid."""
    from pos_uniformes.utils.config import runtime_base_dir

    raiz = runtime_base_dir().parent  # carpeta que contiene el paquete pos_uniformes
    kwargs: dict = {"cwd": str(raiz), "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen([sys.executable, "-m", "pos_uniformes.scripts.telegram_bot"], **kwargs)
    return proc.pid


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    reiniciar = "--reiniciar" in argv
    from pos_uniformes.scripts.telegram_bot import latido_fresco
    from pos_uniformes.services import telegram_service

    if not telegram_service.token_configurado() or not telegram_service.chat_id_configurado():
        print("Telegram no configurado en esta PC; el vigía no hace nada.")
        return 0
    accion = decidir(fresco=latido_fresco(), reiniciar=reiniciar)
    if accion == "nada":
        print("Bot vivo.")
        return 0
    if accion == "reiniciar" or not latido_fresco():
        matar(_pid_guardado())
        time.sleep(2)
    pid = levantar()
    print(f"Bot levantado (pid {pid}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
