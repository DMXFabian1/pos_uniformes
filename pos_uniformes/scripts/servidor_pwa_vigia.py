"""Vigía del servidor de la PWA (PC principal de la tienda).

    python -m pos_uniformes.scripts.servidor_pwa_vigia [--reiniciar]

Lo corre una tarea de Windows al iniciar sesión y cada 5 min:
- si el servidor responde en /health, no hace nada;
- si no responde (no está, se colgó, cerraron la ventana), lo levanta SIN
  ventana; si había un proceso pegado, lo mata primero;
- `--reiniciar` fuerza matar y levantar (lo usa la actualización para que
  la PWA tome el código nuevo).

Así los celulares siempre encuentran http://192.168.0.10:8000/app sin que
nadie tenga que dejar una ventana negra abierta.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

PUERTO = int(os.environ.get("POS_PWA_PUERTO", "8000"))
URL_SALUD = f"http://127.0.0.1:{PUERTO}/health"


def decidir(*, vivo: bool, reiniciar: bool) -> str:
    """'nada' | 'levantar' | 'reiniciar' (puro, testeable)."""
    if reiniciar:
        return "reiniciar"
    return "nada" if vivo else "levantar"


def responde(timeout: float = 4.0) -> bool:
    """¿El servidor contesta ya? (basta con que abra: 'degradado' cuenta)."""
    from urllib.request import urlopen

    try:
        with urlopen(URL_SALUD, timeout=timeout) as r:  # noqa: S310 — localhost
            return 200 <= r.status < 500
    except Exception:  # noqa: BLE001
        return False


def ruta_pid() -> Path:
    from pos_uniformes.utils.config import runtime_base_dir

    return runtime_base_dir() / "data" / "servidor_pwa.pid"


def _pid_guardado() -> int | None:
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


def comando() -> list[str]:
    return [
        sys.executable, "-m", "uvicorn", "pos_uniformes.api.main:app",
        "--host", "0.0.0.0", "--port", str(PUERTO),
    ]


def levantar() -> int:
    """Arranca uvicorn en segundo plano, sin consola. Devuelve el pid."""
    from pos_uniformes.utils.config import runtime_base_dir

    raiz = runtime_base_dir().parent  # carpeta que contiene el paquete pos_uniformes
    kwargs: dict = {"cwd": str(raiz), "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(comando(), **kwargs)
    try:
        p = ruta_pid()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(proc.pid), encoding="utf-8")
    except Exception:  # noqa: BLE001 — el servidor ya arrancó; el pid es extra
        pass
    return proc.pid


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    accion = decidir(vivo=responde(), reiniciar="--reiniciar" in argv)
    if accion == "nada":
        print(f"Servidor PWA vivo en el puerto {PUERTO}.")
        return 0
    matar(_pid_guardado())
    time.sleep(2)
    pid = levantar()
    # Le damos unos segundos y confirmamos que ya contesta.
    for _ in range(10):
        time.sleep(1)
        if responde(timeout=2.0):
            print(f"Servidor PWA levantado (pid {pid}). Celulares: http://192.168.0.10:{PUERTO}/app")
            return 0
    print(f"Servidor PWA levantado (pid {pid}) pero todavia no contesta; revisa en un minuto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
