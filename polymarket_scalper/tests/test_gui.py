import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROYECTO = Path(__file__).resolve().parents[1]


def _hay_entorno_grafico() -> bool:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("DISPLAY")) or shutil.which("xvfb-run") is not None or sys.platform in ("win32", "darwin")


def test_gui_module_imports_without_a_display():
    """Lo que no depende de Tkinter debe poder importarse siempre."""
    from scalper.gui import COLOR, Proceso, _dato_mas_reciente, _entorno
    assert {"fondo", "acento", "ok", "error"} <= set(COLOR)
    assert _entorno()["PYTHONUTF8"] == "1"
    assert _dato_mas_reciente(Path("/no/existe")) is None
    p = Proceso("bot", ["--help"], PROYECTO, __import__("queue").Queue())
    assert not p.vivo
    p.detener()                                   # detener algo que no corre no debe fallar


@pytest.mark.skipif(not _hay_entorno_grafico(), reason="hace falta un entorno gráfico")
def test_gui_window_builds_and_closes():
    """La ventana se construye entera y se cierra sola, sin errores de Tkinter."""
    codigo = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "from pathlib import Path\n"
        "from scalper.gui import lanzar\n"
        "sys.exit(lanzar(Path(r'%s'), 'config.yaml', cerrar_tras_ms=900))\n" % (PROYECTO, PROYECTO)
    )
    orden = [sys.executable, "-c", codigo]
    if not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        orden = ["xvfb-run", "-a", "--server-args=-screen 0 1100x760x24", *orden]
    r = subprocess.run(orden, capture_output=True, text=True, timeout=90, cwd=str(PROYECTO))
    assert r.returncode == 0, f"la ventana falló:\n{r.stdout}\n{r.stderr}"
    assert "Traceback" not in r.stderr
