"""La versión que se ve sale del último cambio, no de un archivo subido a mano.

Daniel, 2026-11-06: «el sistema de versiones sigue viéndose así, está mal ¿no?»
— la cabecera del kiosko decía «Version 2026.11.11», un número quieto desde
el 7 de septiembre que por casualidad parecía una fecha de la otra semana.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.utils import app_metadata as meta


class VersionVisibleTests(unittest.TestCase):
    def test_el_sello_se_dice_como_fecha_y_clave(self) -> None:
        with patch.object(meta, "sello_del_codigo", return_value="2026.11.06+6ba73b01"):
            self.assertEqual(meta.version_visible(), "6 nov · 6ba73b01")
            self.assertEqual(meta.app_build_label(), "Versión 6 nov · 6ba73b01")
            self.assertEqual(meta.satellite_build_label(), "Versión 6 nov · 6ba73b01")

    def test_un_sello_raro_se_ensena_tal_cual(self) -> None:
        with patch.object(meta, "sello_del_codigo", return_value="2026.11.11"):
            self.assertEqual(meta.version_visible(), "2026.11.11")
        with patch.object(meta, "sello_del_codigo", return_value="2026.13.40+abc1234"):
            self.assertEqual(meta.version_visible(), "2026.13.40+abc1234")

    def test_sin_sello_queda_el_archivo_de_siempre(self) -> None:
        with patch.object(meta, "sello_del_codigo", return_value=""), \
                patch.object(meta, "app_version", return_value="2026.04.06"):
            self.assertEqual(meta.version_visible(), "2026.04.06")
            self.assertEqual(meta.app_build_label(), "Version 2026.04.06")

    def test_en_el_kiosko_manda_el_version_txt_junto_al_exe(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "VERSION.txt").write_text("2026.11.06+6ba73b01\n", encoding="utf-8")
            with patch.object(sys, "frozen", True, create=True), \
                    patch.object(sys, "executable", str(Path(d) / "Kiosko.exe")), \
                    patch.object(meta, "_sello_de_git", return_value="2020.01.01+0000000"):
                self.assertEqual(meta.sello_del_codigo(), "2026.11.06+6ba73b01")

    def test_corriendo_del_codigo_lo_dice_git(self) -> None:
        # Este repo: el sello existe, tiene la forma publicada y trae la clave de HEAD.
        import subprocess

        meta._sello_de_git.cache_clear()
        sello = meta.sello_del_codigo()
        self.assertRegex(sello, r"^\d{4}\.\d{2}\.\d{2}\+[0-9a-f]{6,40}$")
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(meta.project_root()),
                              capture_output=True, text=True).stdout.strip()
        self.assertTrue(sello.endswith("+" + head), (sello, head))

    def test_sin_git_no_truena(self) -> None:
        meta._sello_de_git.cache_clear()
        with patch.object(meta.subprocess, "run", side_effect=FileNotFoundError("git")):
            self.assertEqual(meta._sello_de_git("/no/existe"), "")
        meta._sello_de_git.cache_clear()


class BuildPublicaFechaYCommitTests(unittest.TestCase):
    def test_lo_publicado_es_la_fecha_del_ultimo_cambio_mas_el_commit(self) -> None:
        texto = (meta.project_root() / "scripts" / "build_presupuestos_satelite_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("--date=format:%Y.%m.%d", texto)
        self.assertIn('"$fecha+$commit"', texto)
        # Los kioskos y abrir_pos.bat buscan el commit dentro de lo publicado.
        self.assertIn("rev-parse --short HEAD", texto)


if __name__ == "__main__":
    unittest.main()
