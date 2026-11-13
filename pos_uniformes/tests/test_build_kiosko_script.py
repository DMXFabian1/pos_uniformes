"""El build del kiosko de presupuestos solo corre pruebas que existen.

2026-11-13: al retirar Presupuestos del POS se borró
tests/test_quote_selection_helper.py, pero el .ps1 la seguía listando y
`python -m unittest` fallaba antes de PyInstaller.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[1]
_SCRIPT = _RAIZ / "scripts" / "build_presupuestos_satelite_windows.ps1"


class BuildKioskoScriptTests(unittest.TestCase):
    def test_cada_modulo_de_prueba_listado_existe(self) -> None:
        texto = _SCRIPT.read_text(encoding="utf-8")
        modulos = re.findall(r"\btests\.(test_[A-Za-z0-9_]+)", texto)
        self.assertTrue(modulos, "el script ya no lista pruebas")
        faltan = [m for m in modulos if not (_RAIZ / "tests" / f"{m}.py").exists()]
        self.assertEqual(faltan, [])


if __name__ == "__main__":
    unittest.main()
