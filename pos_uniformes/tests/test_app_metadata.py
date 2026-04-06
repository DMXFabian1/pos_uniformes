from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
