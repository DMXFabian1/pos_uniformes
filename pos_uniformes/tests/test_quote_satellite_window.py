from __future__ import annotations

import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow


class QuoteSatelliteWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_catalog_search_refresh_uses_single_debounce_timer(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        callback = Mock()
        window.catalog_browser_debounce_timer.timeout.disconnect()
        window.catalog_browser_debounce_timer.timeout.connect(callback)

        window._schedule_catalog_browser_refresh()
        window._schedule_catalog_browser_refresh()
        QTest.qWait(window.catalog_browser_debounce_timer.interval() + 80)

        self.assertEqual(callback.call_count, 1)

    def test_catalog_immediate_refresh_cancels_pending_debounce(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        callback = Mock()
        window._run_catalog_browser_refresh = callback
        window.catalog_browser_debounce_timer.stop()

        window._schedule_catalog_browser_refresh()
        window._handle_catalog_browser_filters_changed()
        QTest.qWait(window.catalog_browser_debounce_timer.interval() + 80)

        self.assertEqual(callback.call_count, 1)

    def test_catalog_browser_limits_visible_rows_to_single_page(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        row_views = tuple(
            SimpleNamespace(
                sku=f"SKU-{index:03d}",
                values=(f"SKU-{index:03d}", "Primaria", "General", "Producto", "Prenda", "U", "Blanco", "199.00"),
            )
            for index in range(60)
        )
        summary = SimpleNamespace(status_label="60 producto(s) visibles")

        with patch(
            "pos_uniformes.ui.quote_satellite_window.build_quote_catalog_browser",
            return_value=(row_views, summary),
        ):
            window._refresh_catalog_browser()

        self.assertEqual(window.catalog_table.rowCount(), 25)
        self.assertEqual(window.catalog_pagination_label.text(), "Mostrando 1-25 de 60 | Pagina 1 de 3")
        self.assertFalse(window.catalog_previous_page_button.isEnabled())
        self.assertTrue(window.catalog_next_page_button.isEnabled())

    def test_add_from_catalog_keeps_current_page(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        window.catalog_snapshot_rows = [{"sku": "SKU000001"}]
        window.catalog_table.setRowCount(1)
        window.catalog_table.setColumnCount(1)
        window.catalog_table.setCurrentCell(0, 0)

        window._set_page("catalog")
        with patch.object(window, "_add_quote_item_by_sku") as add_item:
            window._handle_add_catalog_selection_to_quote()

        add_item.assert_called_once_with("SKU000001", 1)
        self.assertEqual(window.current_page_key, "catalog")

    def test_add_from_guided_keeps_current_page(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        window.guided_selected_sku = "SKU000002"
        window.guided_qty_spin.setValue(3)

        window._set_page("guided")
        with patch.object(window, "_add_quote_item_by_sku") as add_item:
            window._handle_add_guided_selection_to_quote()

        add_item.assert_called_once_with("SKU000002", 3)
        self.assertEqual(window.current_page_key, "guided")
        self.assertEqual(window.guided_qty_spin.value(), 1)

    def test_add_from_kiosk_keeps_current_page(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        window.lookup_snapshot = SimpleNamespace(sku="SKU000003")

        window._set_page("kiosk")
        with patch.object(window, "_add_quote_item_by_sku") as add_item:
            window._handle_add_lookup_to_quote()

        add_item.assert_called_once_with("SKU000003", 1)
        self.assertEqual(window.current_page_key, "kiosk")


if __name__ == "__main__":
    unittest.main()
