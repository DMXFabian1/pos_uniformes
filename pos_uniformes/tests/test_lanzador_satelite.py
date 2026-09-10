"""El lanzador del kiosko no debe dejar un .exe a medias.

Un robocopy interrumpido (red, antivirus) dejaba el programa truncado y,
como VERSION.txt ya decía la versión nueva, el kiosko quedaba atorado con
"Could not load PyInstaller's embedded PKG archive" (2026-09-10).
"""

from __future__ import annotations

import unittest
from pathlib import Path

_PS1 = Path(__file__).resolve().parents[1] / "scripts" / "lanzador_satelite.ps1"
_FORZAR = Path(__file__).resolve().parents[1] / "scripts" / "forzar_update_satelite.bat"


class LanzadorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.texto = _PS1.read_text(encoding="utf-8", errors="ignore")

    def test_la_version_se_escribe_hasta_el_final(self) -> None:
        # robocopy no copia VERSION.txt...
        self.assertIn("/XF VERSION.txt", self.texto)
        # ...y solo se copia si la copia quedó completa.
        i_ok = self.texto.index("if ($copiaOk)")
        i_version = self.texto.index('Copy-Item (Join-Path $share "VERSION.txt")')
        self.assertLess(i_ok, i_version)

    def test_verifica_el_tamano_del_programa(self) -> None:
        self.assertIn("$exeRemoto.Length", self.texto)
        self.assertIn("$codigo = $LASTEXITCODE", self.texto)
        self.assertIn("-lt 8", self.texto)  # robocopy: 8 o más es error

    def test_recupera_un_exe_incompleto_aunque_la_version_coincida(self) -> None:
        self.assertIn("quedo incompleto", self.texto)
        # La red de seguridad corre antes de arrancar el programa.
        self.assertLess(self.texto.index("quedo incompleto"), self.texto.index("Start-Process $exe.FullName"))


class ReparadorTests(unittest.TestCase):
    """El kiosko se repara solo, sin depender de la PC principal."""

    def test_el_lanzador_se_lleva_el_reparador_al_kiosko(self) -> None:
        texto = _PS1.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("reparar_satelite.bat", texto)

    def test_el_reparador_borra_la_marca_y_abre_el_lanzador(self) -> None:
        rep = _PS1.parent / "reparar_satelite.bat"
        texto = rep.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("VERSION.txt", texto)
        self.assertIn("taskkill", texto)
        self.assertIn("lanzador_satelite.bat", texto)

    def test_el_build_lo_publica(self) -> None:
        build = (_PS1.parent / "build_presupuestos_satelite_windows.ps1").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("reparar_satelite.bat", build)


class ForzarUpdateTests(unittest.TestCase):
    def test_borra_la_marca_de_version(self) -> None:
        texto = _FORZAR.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("VERSION.txt", texto)
        self.assertIn("del /q", texto)


if __name__ == "__main__":
    unittest.main()
