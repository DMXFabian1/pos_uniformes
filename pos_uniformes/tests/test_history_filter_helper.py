from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.history_filter_helper import build_history_type_options


class HistoryFilterHelperTests(unittest.TestCase):
    def test_builds_all_history_type_options(self) -> None:
        options = build_history_type_options("")

        self.assertEqual(options[0], ("Todos", ""))
        self.assertTrue(any(value.startswith("inventory:") for _, value in options))
        self.assertTrue(any(value.startswith("catalog:") for _, value in options))

    def test_builds_inventory_only_history_type_options(self) -> None:
        options = build_history_type_options("inventory")

        self.assertEqual(options[0], ("Todos", ""))
        self.assertTrue(all(not value.startswith("catalog:") for _, value in options))


if __name__ == "__main__":
    unittest.main()
