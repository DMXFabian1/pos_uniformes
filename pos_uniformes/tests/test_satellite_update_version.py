"""La versión "instalada" del satélite es el VERSION.txt que deja el lanzador.

Regresión 2026-09-08: al publicar VERSION.txt como versión+commit, la app
comparaba contra su VERSION interno y avisaba de actualización en cada
arranque aunque ya la tuviera.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services import satellite_update_service as upd


class VersionLocalTests(unittest.TestCase):
    def test_en_dev_usa_version_del_repo(self) -> None:
        with patch.object(upd, "_version_txt_instalada", return_value=None), patch(
            "pos_uniformes.utils.app_metadata.app_version", return_value="2026.11.11"
        ):
            self.assertEqual(upd.version_local(), "2026.11.11")

    def test_empaquetado_lee_version_txt_junto_al_exe(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "VERSION.txt").write_text("2026.11.11+abc123\n", encoding="utf-8")
            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "executable", str(Path(d) / "PresupuestosSatelite.exe")
            ):
                self.assertEqual(upd.version_local(), "2026.11.11+abc123")

    def test_empaquetado_sin_version_txt_cae_a_version(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "executable", str(Path(d) / "PresupuestosSatelite.exe")
            ), patch("pos_uniformes.utils.app_metadata.app_version", return_value="2026.11.11"):
                self.assertEqual(upd.version_local(), "2026.11.11")

    def test_instalada_igual_a_publicada_no_avisa(self) -> None:
        with patch.object(upd, "version_local", return_value="2026.11.11+abc123"), patch.object(
            upd, "version_remota", return_value="2026.11.11+abc123"
        ):
            local, remota, hay = upd.estado_actualizacion()
        self.assertFalse(hay)

    def test_publicada_distinta_si_avisa(self) -> None:
        with patch.object(upd, "version_local", return_value="2026.11.11+abc123"), patch.object(
            upd, "version_remota", return_value="2026.11.11+def456"
        ):
            self.assertTrue(upd.estado_actualizacion()[2])


if __name__ == "__main__":
    unittest.main()
