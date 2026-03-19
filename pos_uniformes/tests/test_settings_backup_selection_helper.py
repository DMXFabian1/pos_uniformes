from __future__ import annotations

from pathlib import Path
import unittest

from pos_uniformes.ui.helpers.settings_backup_selection_helper import (
    resolve_selected_settings_backup_path,
)


class SettingsBackupSelectionHelperTests(unittest.TestCase):
    def test_resolve_selected_settings_backup_path(self) -> None:
        self.assertEqual(
            resolve_selected_settings_backup_path(current_row=0, raw_path="/tmp/demo.dump"),
            Path("/tmp/demo.dump"),
        )
        self.assertIsNone(resolve_selected_settings_backup_path(current_row=-1, raw_path="/tmp/demo.dump"))
        self.assertIsNone(resolve_selected_settings_backup_path(current_row=0, raw_path=None))


if __name__ == "__main__":
    unittest.main()
