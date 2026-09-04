from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.utils import app_metadata


class AppMetadataTests(unittest.TestCase):
    def test_app_version_reads_version_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "VERSION").write_text("2026.04.06\n", encoding="utf-8")

            with patch("pos_uniformes.utils.app_metadata.project_root", return_value=root):
                self.assertEqual(app_metadata.app_version(), "2026.04.06")
                self.assertEqual(app_metadata.app_build_label(), "Version 2026.04.06")
                self.assertEqual(app_metadata.satellite_display_name(), "Kiosko de Presupuestos")
                self.assertEqual(app_metadata.satellite_build_label(), "Version 2026.04.06")

    def test_app_version_falls_back_when_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("pos_uniformes.utils.app_metadata.project_root", return_value=root):
                self.assertEqual(app_metadata.app_version(), app_metadata.DEFAULT_APP_VERSION)

    def test_app_icon_path_prefers_brand_logo_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            logo_path = root / "assets" / "customer_card_template" / "brand" / "store-logo.PNG"
            logo_path.parent.mkdir(parents=True, exist_ok=True)
            logo_path.write_bytes(b"png")

            with patch("pos_uniformes.utils.app_metadata.project_root", return_value=root):
                self.assertEqual(app_metadata.app_icon_path(), logo_path)

    def test_app_icon_path_prefers_windows_ico_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ico_path = root / "assets" / "app_icon.ico"
            ico_path.parent.mkdir(parents=True, exist_ok=True)
            ico_path.write_bytes(b"ico")
            logo_path = root / "assets" / "customer_card_template" / "brand" / "store-logo.PNG"
            logo_path.parent.mkdir(parents=True, exist_ok=True)
            logo_path.write_bytes(b"png")

            with patch("pos_uniformes.utils.app_metadata.project_root", return_value=root):
                self.assertEqual(app_metadata.app_windows_icon_path(), ico_path)
                self.assertEqual(app_metadata.app_icon_path(), ico_path)

    def test_satellite_windows_icon_path_prefers_kiosk_icon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            kiosk_ico_path = root / "assets" / "kiosk_app_icon.ico"
            kiosk_ico_path.parent.mkdir(parents=True, exist_ok=True)
            kiosk_ico_path.write_bytes(b"kiosk")
            app_ico_path = root / "assets" / "app_icon.ico"
            app_ico_path.write_bytes(b"app")

            with patch("pos_uniformes.utils.app_metadata.project_root", return_value=root):
                self.assertEqual(app_metadata.satellite_windows_icon_path(), kiosk_ico_path)


class AppVersionFrozenTests(unittest.TestCase):
    """El bug real en tienda: dentro del exe (PyInstaller) VERSION vive en
    la raíz del bundle (sys._MEIPASS); app_version() caía al DEFAULT y la
    app creía por siempre que había una actualización disponible."""

    def tearDown(self) -> None:
        if hasattr(sys, "_MEIPASS"):
            del sys._MEIPASS

    def test_empaquetado_lee_el_version_del_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as bundle:
            (Path(bundle) / "VERSION").write_text("2099.01.01\n", encoding="utf-8")
            sys._MEIPASS = bundle
            self.assertEqual(app_metadata.app_version(), "2099.01.01")

    def test_empaquetado_sin_version_cae_al_repo_y_luego_al_default(self) -> None:
        with tempfile.TemporaryDirectory() as bundle:
            sys._MEIPASS = bundle  # bundle sin archivo VERSION
            esperado = (app_metadata.project_root() / "VERSION").read_text().strip()
            self.assertEqual(app_metadata.app_version(), esperado)


if __name__ == "__main__":
    unittest.main()
