from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pos_uniformes.utils.pyinstaller_data_helper import collect_tree_datas


class PyInstallerDataHelperTests(unittest.TestCase):
    def test_collect_tree_datas_preserves_asset_subdirectories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir) / "assets"
            qr_icons_dir = source_root / "qr_icons"
            qr_icons_dir.mkdir(parents=True)
            (qr_icons_dir / "default.png").write_bytes(b"png")

            datas = collect_tree_datas(source_root, "pos_uniformes/assets")

            self.assertEqual(
                datas,
                [
                    (
                        str((qr_icons_dir / "default.png").resolve()),
                        "pos_uniformes/assets/qr_icons",
                    )
                ],
            )

    def test_collect_tree_datas_includes_python_files_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir) / "migrations"
            versions_dir = source_root / "versions"
            versions_dir.mkdir(parents=True)
            (source_root / "env.py").write_text("# env\n", encoding="utf-8")
            (versions_dir / "123_revision.py").write_text("# revision\n", encoding="utf-8")
            (versions_dir / "123_revision.pyc").write_bytes(b"compiled")
            (versions_dir / ".DS_Store").write_bytes(b"noise")

            datas = collect_tree_datas(
                source_root,
                "pos_uniformes/migrations",
                include_python_files=True,
            )

            self.assertEqual(
                datas,
                [
                    (
                        str((source_root / "env.py").resolve()),
                        "pos_uniformes/migrations",
                    ),
                    (
                        str((versions_dir / "123_revision.py").resolve()),
                        "pos_uniformes/migrations/versions",
                    ),
                ],
            )

    def test_collect_tree_datas_skips_python_files_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir) / "assets"
            source_root.mkdir()
            (source_root / "logo.png").write_bytes(b"png")
            (source_root / "helper.py").write_text("# helper\n", encoding="utf-8")

            datas = collect_tree_datas(source_root, "pos_uniformes/assets")

            self.assertEqual(
                datas,
                [
                    (
                        str((source_root / "logo.png").resolve()),
                        "pos_uniformes/assets",
                    )
                ],
            )


if __name__ == "__main__":
    unittest.main()
