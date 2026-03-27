from __future__ import annotations

import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QTableWidgetItem

from pos_uniformes.ui.main_window import CATALOG_PAGE_SIZE, INVENTORY_PAGE_SIZE, MainWindow


class MainWindowSnapshotCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_catalog_snapshot_cache_reuses_rows_until_invalidated(self) -> None:
        window = MainWindow(user_id=1)
        sentinel_session = object()
        window._invalidate_listing_snapshot_caches()

        with patch(
            "pos_uniformes.ui.main_window.load_catalog_snapshot_rows",
            return_value=[{"variante_id": 1, "sku": "SKU-001"}],
        ) as loader:
            first_rows = window._load_catalog_snapshot_rows(sentinel_session)
            second_rows = window._load_catalog_snapshot_rows(sentinel_session)

            self.assertEqual(first_rows, second_rows)
            self.assertEqual(loader.call_count, 1)

            window._invalidate_listing_snapshot_caches(catalog=True, inventory=False)
            reloaded_rows = window._load_catalog_snapshot_rows(sentinel_session)

            self.assertEqual(reloaded_rows, first_rows)
            self.assertEqual(loader.call_count, 2)

    def test_inventory_snapshot_cache_reuses_rows_until_invalidated(self) -> None:
        window = MainWindow(user_id=1)
        sentinel_session = object()
        window._invalidate_listing_snapshot_caches()

        with patch(
            "pos_uniformes.ui.main_window.load_inventory_snapshot_rows",
            return_value=[{"variante_id": 2, "sku": "SKU-002"}],
        ) as loader:
            first_rows = window._load_inventory_snapshot_rows(sentinel_session)
            second_rows = window._load_inventory_snapshot_rows(sentinel_session)

            self.assertEqual(first_rows, second_rows)
            self.assertEqual(loader.call_count, 1)

            window._invalidate_listing_snapshot_caches(catalog=False, inventory=True)
            reloaded_rows = window._load_inventory_snapshot_rows(sentinel_session)

            self.assertEqual(reloaded_rows, first_rows)
            self.assertEqual(loader.call_count, 2)

    def test_catalog_search_refresh_uses_single_debounce_timer(self) -> None:
        window = MainWindow(user_id=1)
        callback = Mock()
        window._run_catalog_filter_refresh = callback

        window._schedule_catalog_filter_refresh()
        window._schedule_catalog_filter_refresh()
        QTest.qWait(window.catalog_filter_debounce_timer.interval() + 80)

        self.assertEqual(callback.call_count, 1)

    def test_inventory_search_refresh_uses_single_debounce_timer(self) -> None:
        window = MainWindow(user_id=1)
        callback = Mock()
        window._run_inventory_filter_refresh = callback

        window._schedule_inventory_filter_refresh()
        window._schedule_inventory_filter_refresh()
        QTest.qWait(window.inventory_filter_debounce_timer.interval() + 80)

        self.assertEqual(callback.call_count, 1)

    def test_catalog_immediate_refresh_cancels_pending_debounce(self) -> None:
        window = MainWindow(user_id=1)
        callback = Mock()
        window._run_catalog_filter_refresh = callback

        window._schedule_catalog_filter_refresh()
        window._handle_catalog_filters_changed()
        QTest.qWait(window.catalog_filter_debounce_timer.interval() + 80)

        self.assertEqual(callback.call_count, 1)

    def test_inventory_immediate_refresh_cancels_pending_debounce(self) -> None:
        window = MainWindow(user_id=1)
        callback = Mock()
        window._run_inventory_filter_refresh = callback

        window._schedule_inventory_filter_refresh()
        window._handle_inventory_filters_changed()
        QTest.qWait(window.inventory_filter_debounce_timer.interval() + 80)

        self.assertEqual(callback.call_count, 1)

    def test_catalog_type_filter_accepts_macro_value_without_accent(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_type_filter_combo.set_items(
            [
                ("Básico", "Básico"),
                ("Deportivo", "Deportivo"),
            ]
        )

        window.catalog_type_filter_combo.set_selected_values(["Basico"])

        self.assertEqual(window.catalog_type_filter_combo.selected_values(), {"Básico"})

    def test_refresh_catalog_does_not_force_explicit_column_resize(self) -> None:
        window = MainWindow(user_id=1)
        catalog_row = {"variante_id": 1, "sku": "SKU-001"}
        table_row_view = SimpleNamespace(
            values=[
                "SKU-001",
                "General",
                "Deportivo",
                "Pants",
                "Marca Norte",
                "Pants Deportivo",
                "16",
                "Azul",
                "$219.00",
                "6",
                "2",
                "Activa",
            ],
            row_tone=None,
            stock_tone="positive",
            layaway_tone="warning",
            status_tone="positive",
        )
        summary_view = SimpleNamespace(results_summary="1 resultado", active_filters_summary="Sin filtros")

        with patch.object(window, "_load_catalog_snapshot_rows", return_value=[catalog_row]), patch(
            "pos_uniformes.ui.main_window.filter_visible_catalog_rows",
            return_value=[catalog_row],
        ), patch(
            "pos_uniformes.ui.main_window.build_catalog_table_row_views",
            return_value=[table_row_view],
        ), patch(
            "pos_uniformes.ui.main_window.build_catalog_summary_view",
            return_value=summary_view,
        ), patch("PyQt6.QtWidgets.QTableWidget.resizeColumnsToContents") as resize_mock:
            window._refresh_catalog()

        resize_mock.assert_not_called()

    def test_refresh_inventory_does_not_force_explicit_column_resize(self) -> None:
        window = MainWindow(user_id=1)
        inventory_row = {"variante_id": 2, "sku": "SKU-002"}
        table_row_view = SimpleNamespace(
            values=[
                "SKU-002",
                "Pants Deportivo",
                "16",
                "Azul",
                "6",
                "2",
                "Activa",
                "OK",
            ],
            row_tone=None,
            variant_id=2,
            stock_tone="positive",
            committed_tone="warning",
            status_tone="positive",
            qr_tone="positive",
        )
        summary_view = SimpleNamespace(
            out_counter=SimpleNamespace(text="0", tone="positive"),
            low_counter=SimpleNamespace(text="0", tone="positive"),
            qr_pending_counter=SimpleNamespace(text="0", tone="positive"),
            inactive_counter=SimpleNamespace(text="0", tone="positive"),
            results_summary="1 resultado",
        )

        with patch.object(window, "_load_inventory_snapshot_rows", return_value=[inventory_row]), patch(
            "pos_uniformes.ui.main_window.filter_visible_inventory_rows",
            return_value=[inventory_row],
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_table_row_views",
            return_value=[table_row_view],
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_summary_view",
            return_value=summary_view,
        ), patch.object(window, "_build_inventory_active_filters_summary", return_value="Sin filtros"), patch.object(
            window, "_sync_inventory_table_selection"
        ) as sync_mock, patch.object(window, "_refresh_inventory_overview") as overview_mock, patch(
            "PyQt6.QtWidgets.QTableWidget.resizeColumnsToContents"
        ) as resize_mock:
            window._refresh_inventory_table()

        resize_mock.assert_not_called()
        sync_mock.assert_called_once()
        overview_mock.assert_called_once()

    def test_refresh_inventory_limits_visible_rows_to_single_page(self) -> None:
        window = MainWindow(user_id=1)
        filtered_rows = [{"variante_id": index, "sku": f"SKU-{index:03d}"} for index in range(60)]
        table_row_view = SimpleNamespace(
            values=[
                "SKU-000",
                "Pants Deportivo",
                "16",
                "Azul",
                "6",
                "2",
                "Activa",
                "OK",
            ],
            row_tone=None,
            variant_id=0,
            stock_tone="positive",
            committed_tone="warning",
            status_tone="positive",
            qr_tone="positive",
        )
        summary_view = SimpleNamespace(
            out_counter=SimpleNamespace(text="0", tone="positive"),
            low_counter=SimpleNamespace(text="0", tone="positive"),
            qr_pending_counter=SimpleNamespace(text="0", tone="positive"),
            inactive_counter=SimpleNamespace(text="0", tone="positive"),
            results_summary="60 resultados",
        )

        with patch.object(window, "_load_inventory_snapshot_rows", return_value=filtered_rows), patch(
            "pos_uniformes.ui.main_window.filter_visible_inventory_rows",
            return_value=filtered_rows,
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_table_row_views",
            return_value=[table_row_view] * INVENTORY_PAGE_SIZE,
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_summary_view",
            return_value=summary_view,
        ), patch.object(window, "_build_inventory_active_filters_summary", return_value="Sin filtros"), patch.object(
            window, "_sync_inventory_table_selection"
        ), patch.object(window, "_refresh_inventory_overview"):
            window._refresh_inventory_table()

        self.assertEqual(len(window.inventory_filtered_rows), 60)
        self.assertEqual(len(window.inventory_rows), INVENTORY_PAGE_SIZE)
        self.assertEqual(window.inventory_pagination_label.text(), "1-25 de 60 | p. 1/3")
        self.assertFalse(window.inventory_previous_page_button.isEnabled())
        self.assertTrue(window.inventory_next_page_button.isEnabled())

    def test_inventory_filter_reset_page_methods_return_to_first_page(self) -> None:
        window = MainWindow(user_id=1)
        window.inventory_page_index = 3
        handle_callback = Mock()
        schedule_callback = Mock()
        window._handle_inventory_filters_changed = handle_callback
        window._schedule_inventory_filter_refresh = schedule_callback

        window._handle_inventory_filters_changed_reset_page()
        self.assertEqual(window.inventory_page_index, 0)
        handle_callback.assert_called_once()

        window.inventory_page_index = 4
        window._schedule_inventory_filter_refresh_reset_page()
        self.assertEqual(window.inventory_page_index, 0)
        schedule_callback.assert_called_once()

    def test_reload_table_widget_restores_updates_and_signals(self) -> None:
        window = MainWindow(user_id=1)
        table = window.catalog_table

        self.assertTrue(table.updatesEnabled())
        self.assertFalse(table.signalsBlocked())

        window._reload_table_widget(
            table,
            row_count=1,
            populate_rows=lambda: table.setItem(0, 0, QTableWidgetItem("SKU-001")),
        )

        self.assertTrue(table.updatesEnabled())
        self.assertFalse(table.signalsBlocked())

    def test_refresh_catalog_limits_visible_rows_to_single_page(self) -> None:
        window = MainWindow(user_id=1)
        filtered_rows = [{"variante_id": index, "sku": f"SKU-{index:03d}"} for index in range(60)]
        summary_view = SimpleNamespace(results_summary="60 resultados", active_filters_summary="Sin filtros")

        def build_row_views(rows: list[dict[str, object]]) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    values=[
                        row["sku"],
                        "General",
                        "Deportivo",
                        "Pants",
                        "Marca Norte",
                        "Pants Deportivo",
                        "16",
                        "Azul",
                        "$219.00",
                        "6",
                        "2",
                        "Activa",
                    ],
                    row_tone=None,
                    stock_tone="positive",
                    layaway_tone="warning",
                    status_tone="positive",
                )
                for row in rows
            ]

        with patch.object(window, "_load_catalog_snapshot_rows", return_value=filtered_rows), patch(
            "pos_uniformes.ui.main_window.filter_visible_catalog_rows",
            return_value=filtered_rows,
        ), patch(
            "pos_uniformes.ui.main_window.build_catalog_table_row_views",
            side_effect=build_row_views,
        ), patch(
            "pos_uniformes.ui.main_window.build_catalog_summary_view",
            return_value=summary_view,
        ):
            window._refresh_catalog()

        self.assertEqual(len(window.catalog_filtered_rows), 60)
        self.assertEqual(len(window.catalog_rows), CATALOG_PAGE_SIZE)
        self.assertEqual(window.catalog_rows[0]["variante_id"], 0)
        self.assertEqual(window.catalog_rows[-1]["variante_id"], CATALOG_PAGE_SIZE - 1)
        self.assertEqual(
            window.catalog_pagination_label.text(),
            "1-25 de 60 | p. 1/3",
        )
        self.assertFalse(window.catalog_previous_page_button.isEnabled())
        self.assertTrue(window.catalog_next_page_button.isEnabled())

    def test_catalog_page_navigation_changes_page_without_resetting_to_selection(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_page_index = 0
        window.catalog_preserve_selection_on_refresh = True
        callback = Mock()
        window._handle_catalog_filters_changed = callback

        window._handle_catalog_next_page()

        self.assertEqual(window.catalog_page_index, 1)
        self.assertFalse(window.catalog_preserve_selection_on_refresh)
        callback.assert_called_once()

    def test_catalog_filter_reset_page_methods_return_to_first_page(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_page_index = 3
        handle_callback = Mock()
        schedule_callback = Mock()
        window._handle_catalog_filters_changed = handle_callback
        window._schedule_catalog_filter_refresh = schedule_callback

        window._handle_catalog_filters_changed_reset_page()
        self.assertEqual(window.catalog_page_index, 0)
        handle_callback.assert_called_once()

        window.catalog_page_index = 4
        window._schedule_catalog_filter_refresh_reset_page()
        self.assertEqual(window.catalog_page_index, 0)
        schedule_callback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
