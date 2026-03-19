from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_crm_selection_helper import (
    resolve_selected_settings_client_id,
    resolve_selected_settings_supplier_id,
)


class SettingsCrmSelectionHelperTests(unittest.TestCase):
    def test_resolve_selected_settings_supplier_id(self) -> None:
        self.assertEqual(resolve_selected_settings_supplier_id(current_row=0, raw_supplier_id="8"), 8)
        self.assertIsNone(resolve_selected_settings_supplier_id(current_row=-1, raw_supplier_id=8))

    def test_resolve_selected_settings_client_id(self) -> None:
        self.assertEqual(resolve_selected_settings_client_id(current_row=0, raw_client_id="11"), 11)
        self.assertIsNone(resolve_selected_settings_client_id(current_row=0, raw_client_id=None))


if __name__ == "__main__":
    unittest.main()
