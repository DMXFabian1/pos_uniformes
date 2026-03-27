from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pos_uniformes.utils.legacy_paths import detect_legacy_sqlite_path


class LegacyPathsTests(unittest.TestCase):
    def test_detect_prefers_database_in_current_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_root = temp_path / "pos_uniformes"
            cwd = temp_path / "runtime"
            home_dir = temp_path / "home"
            project_root.mkdir()
            cwd.mkdir()
            home_dir.mkdir()

            expected = cwd / "productos.db"
            expected.write_text("", encoding="utf-8")

            detected = detect_legacy_sqlite_path(
                project_root=project_root,
                cwd=cwd,
                home_dir=home_dir,
            )

        self.assertEqual(detected, expected.resolve())

    def test_detect_uses_legacy_workspace_snapshot_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_root = temp_path / "pos_uniformes"
            cwd = temp_path / "runtime"
            home_dir = temp_path / "home"
            legacy_data_dir = temp_path / "Gestor_de_Inventarios" / "data"
            project_root.mkdir()
            cwd.mkdir()
            home_dir.mkdir()
            legacy_data_dir.mkdir(parents=True)

            expected = legacy_data_dir / "productos.db"
            expected.write_text("", encoding="utf-8")

            detected = detect_legacy_sqlite_path(
                project_root=project_root,
                cwd=cwd,
                home_dir=home_dir,
            )

        self.assertEqual(detected, expected.resolve())

    def test_detect_falls_back_to_portable_candidate_when_no_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_root = temp_path / "pos_uniformes"
            cwd = temp_path / "runtime"
            home_dir = temp_path / "home"
            project_root.mkdir()
            cwd.mkdir()
            home_dir.mkdir()

            detected = detect_legacy_sqlite_path(
                project_root=project_root,
                cwd=cwd,
                home_dir=home_dir,
            )

        self.assertEqual(detected, (cwd / "productos.db").resolve())
        self.assertNotIn("/Users/", str(detected))


if __name__ == "__main__":
    unittest.main()
