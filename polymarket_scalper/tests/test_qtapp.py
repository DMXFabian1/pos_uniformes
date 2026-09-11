import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROYECTO = Path(__file__).resolve().parents[1]


def _hay_pyqt() -> bool:
    try:
        import PyQt6.QtWidgets  # noqa: F401
    except ImportError:
        return False
    return True


def test_no_hay_identificadores_con_acentos_en_el_codigo():
    """PyQt6 falla al conectar una señal a un método cuyo nombre no es ASCII.

    Costó un fallo de segmentación descubrirlo, así que queda comprobado para todo el paquete.
    """
    malos = []
    for f in sorted((PROYECTO / "scalper").rglob("*.py")):
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            nombre = None
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nombre = n.name
            elif isinstance(n, ast.arg):
                nombre = n.arg
            elif isinstance(n, ast.Name):
                nombre = n.id
            if nombre and not nombre.isascii():
                malos.append(f"{f.relative_to(PROYECTO)}: {nombre}")
    assert not malos, "identificadores con caracteres no ASCII: " + ", ".join(sorted(set(malos)))


@pytest.mark.skipif(not _hay_pyqt(), reason="PyQt6 no está instalado")
def test_la_ventana_de_qt_se_construye_y_se_cierra():
    codigo = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "from pathlib import Path\n"
        "from scalper.qtapp import lanzar, disponible\n"
        "assert disponible()\n"
        "sys.exit(lanzar(Path(r'%s'), 'config.yaml', cerrar_tras_ms=900))\n" % (PROYECTO, PROYECTO)
    )
    entorno = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "SCALPER_SIN_WEB": "1"}
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=120,
                       cwd=str(PROYECTO), env=entorno)
    assert r.returncode == 0, f"la ventana de Qt falló:\n{r.stdout}\n{r.stderr}"
    assert "Traceback" not in r.stderr


@pytest.mark.skipif(not _hay_pyqt(), reason="PyQt6 no está instalado")
def test_piezas_sueltas_de_la_ventana():
    entorno = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "SCALPER_SIN_WEB": "1"}
    codigo = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from scalper.qtapp import Tarjeta, _punto, _dato_mas_reciente, _ESPERANDO, C\n"
        "from pathlib import Path\n"
        "t = Tarjeta('Prueba', 'nota'); t.poner('42', 'otra nota', C['ok'])\n"
        "assert t.valor.text() == '42' and t.nota.text() == 'otra nota'\n"
        "assert not _punto('#0ca30c').isNull()\n"
        "assert _dato_mas_reciente(Path('/no/existe')) is None\n"
        "assert 'El panel aparecerá aquí' in _ESPERANDO and C['fondo'] in _ESPERANDO\n"
        "print('ok')\n" % PROYECTO
    )
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=120,
                       cwd=str(PROYECTO), env=entorno)
    assert r.returncode == 0 and "ok" in r.stdout, f"{r.stdout}\n{r.stderr}"
