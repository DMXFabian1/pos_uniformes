from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pos_uniformes.scripts import windows_run_dev


class WindowsRunDevTests(unittest.TestCase):
    def test_parse_args_defaults(self) -> None:
        args = windows_run_dev.parse_args([])

        self.assertFalse(args.skip_migrations)
        self.assertFalse(args.skip_precheck)
        self.assertFalse(args.dry_run)

    def test_format_elapsed_for_seconds(self) -> None:
        self.assertEqual(windows_run_dev.format_elapsed(0.42), "0.42s")
        self.assertEqual(windows_run_dev.format_elapsed(12.5), "12.5s")
        self.assertEqual(windows_run_dev.format_elapsed(75.25), "1m 15.2s")

    def test_ensure_env_file_copies_example_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            example = root / "pos_uniformes.env.example"
            example.write_text("POS_UNIFORMES_DB_HOST=localhost\n", encoding="utf-8")

            ready = windows_run_dev.ensure_env_file(root, dry_run=False)

            self.assertFalse(ready)
            self.assertTrue((root / "pos_uniformes.env").exists())

    def test_ensure_env_file_returns_true_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pos_uniformes.env").write_text("POS_UNIFORMES_DB_HOST=localhost\n", encoding="utf-8")

            ready = windows_run_dev.ensure_env_file(root, dry_run=False)

            self.assertTrue(ready)


if __name__ == "__main__":
    unittest.main()
