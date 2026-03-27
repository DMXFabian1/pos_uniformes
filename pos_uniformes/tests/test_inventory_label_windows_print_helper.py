from __future__ import annotations

import unittest
from unittest.mock import patch

from pos_uniformes.ui.helpers.inventory_label_windows_print_helper import (
    WindowsInventoryLabelPrinterResolution,
    resolve_windows_inventory_label_printer,
)


class InventoryLabelWindowsPrintHelperTests(unittest.TestCase):
    @patch("pos_uniformes.ui.helpers.inventory_label_windows_print_helper.list_windows_printer_names")
    @patch("pos_uniformes.ui.helpers.inventory_label_windows_print_helper._load_win32_modules")
    def test_uses_preferred_printer_when_available(self, mock_load_modules, mock_list_printers) -> None:
        mock_win32print = type("Win32Print", (), {"GetDefaultPrinter": staticmethod(lambda: "Microsoft Print to PDF")})
        mock_load_modules.return_value = (mock_win32print, object())
        mock_list_printers.return_value = ["Brother QL-800", "Microsoft Print to PDF"]

        resolution = resolve_windows_inventory_label_printer("Brother QL-800")

        self.assertEqual(
            resolution,
            WindowsInventoryLabelPrinterResolution(
                printer_name="Brother QL-800",
                available_printers=["Brother QL-800", "Microsoft Print to PDF"],
                fallback_used=False,
            ),
        )

    @patch("pos_uniformes.ui.helpers.inventory_label_windows_print_helper.list_windows_printer_names")
    @patch("pos_uniformes.ui.helpers.inventory_label_windows_print_helper._load_win32_modules")
    def test_falls_back_to_default_printer_when_preferred_is_missing(self, mock_load_modules, mock_list_printers) -> None:
        mock_win32print = type("Win32Print", (), {"GetDefaultPrinter": staticmethod(lambda: "Microsoft Print to PDF")})
        mock_load_modules.return_value = (mock_win32print, object())
        mock_list_printers.return_value = ["Microsoft Print to PDF"]

        resolution = resolve_windows_inventory_label_printer("Brother QL-800")

        self.assertEqual(resolution.printer_name, "Microsoft Print to PDF")
        self.assertTrue(resolution.fallback_used)


if __name__ == "__main__":
    unittest.main()
