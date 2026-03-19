from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_user_selection_helper import (
    resolve_selected_settings_user_id,
)


class SettingsUserSelectionHelperTests(unittest.TestCase):
    def test_resolve_selected_settings_user_id(self) -> None:
        self.assertEqual(
            resolve_selected_settings_user_id(current_row=0, raw_user_id="7"),
            7,
        )
        self.assertIsNone(resolve_selected_settings_user_id(current_row=-1, raw_user_id=7))
        self.assertIsNone(resolve_selected_settings_user_id(current_row=0, raw_user_id=None))


if __name__ == "__main__":
    unittest.main()
