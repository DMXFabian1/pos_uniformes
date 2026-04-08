from __future__ import annotations

import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QTableWidgetItem

from pos_uniformes.services.active_filter_service import ActiveFilterToken
from pos_uniformes.database.models import RolUsuario
from pos_uniformes.ui.main_window import (
    CATALOG_PAGE_SIZE,
    INVENTORY_PAGE_SIZE,
    MainWindow,
    _catalog_toggle_feedback_action,
)


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

    def test_catalog_toggle_feedback_action_uses_supported_result_keys(self) -> None:
        self.assertEqual(_catalog_toggle_feedback_action(True), "activate")
        self.assertEqual(_catalog_toggle_feedback_action(False), "deactivate")

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

    def test_cash_session_label_hides_expected_amount_from_hero(self) -> None:
        window = MainWindow(user_id=1)
        active_session = SimpleNamespace(id=5, monto_apertura="1000.00")
        resumen = SimpleNamespace(esperado_en_caja="2450.00")

        with patch("pos_uniformes.ui.main_window.CajaService.obtener_sesion_activa", return_value=active_session), patch(
            "pos_uniformes.ui.main_window.CajaService.resumir_sesion",
            return_value=resumen,
        ), patch.object(window, "_is_stale_cash_session", return_value=True):
            window._refresh_cash_session(object())

        self.assertIn("Reactivo inicial $1000.00", window.cash_session_label.text())
        self.assertIn("Corte pendiente", window.cash_session_label.text())
        self.assertNotIn("Esperado", window.cash_session_label.text())

    def test_cashier_role_hides_opening_amount_from_hero(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.CAJERO
        active_session = SimpleNamespace(id=5, monto_apertura="1000.00")

        with patch("pos_uniformes.ui.main_window.CajaService.obtener_sesion_activa", return_value=active_session), patch.object(
            window, "_is_stale_cash_session", return_value=False
        ):
            window._refresh_cash_session(object())

        self.assertEqual(window.cash_session_label.text(), "Rol CAJERO · Caja abierta")
        self.assertNotIn("Reactivo inicial", window.cash_session_label.text())

    def test_cashier_role_hides_manual_discount_controls(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.CAJERO

        window._apply_role_navigation()
        window._refresh_permissions()

        self.assertTrue(window.sale_discount_field_label.isHidden())
        self.assertTrue(window.sale_discount_combo.isHidden())

    def test_admin_role_keeps_manual_discount_controls_visible(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.ADMIN

        window._apply_role_navigation()
        window._refresh_permissions()

        self.assertFalse(window.sale_discount_field_label.isHidden())
        self.assertFalse(window.sale_discount_combo.isHidden())

    def test_quote_cart_table_keeps_cashier_breathing_in_main_window(self) -> None:
        window = MainWindow(user_id=1)

        self.assertEqual(window.quote_cart_table.objectName(), "cashierCartTable")
        self.assertEqual(window.quote_cart_table.verticalHeader().defaultSectionSize(), 48)
        self.assertEqual(window.quote_cart_table.minimumHeight(), 260)

    def test_cashier_role_hides_dashboard_tab(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.CAJERO

        window._apply_role_navigation()

        self.assertFalse(window.tabs.isTabVisible(0))
        self.assertTrue(window.tabs.isTabVisible(1))

    def test_cashier_role_redirects_from_hidden_dashboard_to_cashier(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.CAJERO
        window.tabs.setCurrentIndex(0)

        window._apply_role_navigation()

        self.assertEqual(window.tabs.currentIndex(), 1)

    def test_restore_catalog_selection_after_mutation_clears_stale_selection_when_row_disappears(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_table.setRowCount(1)
        window.catalog_table.setColumnCount(1)
        window.catalog_table.setCurrentCell(0, 0)
        window.catalog_table.selectRow(0)
        window.inventory_table.setRowCount(1)
        window.inventory_table.setColumnCount(1)
        first_item = QTableWidgetItem("SKU-001")
        first_item.setData(0x0100, 101)
        window.inventory_table.setItem(0, 0, first_item)
        window.inventory_table.setCurrentCell(0, 0)
        window.inventory_table.selectRow(0)

        with patch.object(window, "_select_catalog_variant", return_value=False):
            window._restore_catalog_selection_after_mutation(101)

        self.assertEqual(window.catalog_table.currentRow(), -1)
        self.assertEqual(window.inventory_table.currentRow(), -1)
        self.assertIn("Selecciona una presentacion", window.catalog_selection_label.text())

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

    def test_catalog_active_filter_chips_show_search_and_linea_tokens(self) -> None:
        window = MainWindow(user_id=1)
        window._handle_catalog_filters_changed = Mock()
        window.catalog_search_input.blockSignals(True)
        window.catalog_search_input.setText("pants")
        window.catalog_search_input.blockSignals(False)
        window.catalog_type_filter_combo.set_items(
            [
                ("Deportivo", "Deportivo"),
                ("Oficial", "Oficial"),
            ]
        )
        window.catalog_type_filter_combo.set_selected_values(["Deportivo"])

        window._refresh_catalog_active_filter_chips()

        layout = window.catalog_active_filters_flow_layout
        texts = [layout.itemAt(index).widget().text() for index in range(layout.count())]
        self.assertFalse(window.catalog_active_filters_wrap.isHidden())
        self.assertEqual(
            texts,
            ['Texto: "pants"  ×', "Linea: Deportivo  ×"],
        )

    def test_catalog_and_inventory_hide_category_filters(self) -> None:
        window = MainWindow(user_id=1)

        self.assertTrue(window.catalog_category_filter_combo.isHidden())
        self.assertTrue(window.inventory_category_filter_combo.isHidden())
        self.assertFalse(window.catalog_type_filter_combo.isHidden())
        self.assertFalse(window.inventory_type_filter_combo.isHidden())

    def test_hidden_category_filter_does_not_generate_active_chips(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_category_filter_combo.set_items([("Básico", "Básico")])
        window.catalog_category_filter_combo.set_selected_values(["Básico"])
        window.inventory_category_filter_combo.set_items([("Básico", "Básico")])
        window.inventory_category_filter_combo.set_selected_values(["Básico"])

        self.assertEqual(window._catalog_active_filter_tokens(), [])
        self.assertEqual(window._inventory_active_filter_tokens(), [])

    def test_catalog_hides_status_filter_and_forces_active_rows(self) -> None:
        window = MainWindow(user_id=1)
        snapshot_rows = [{"variante_id": 1, "sku": "SKU-001"}]
        summary_view = SimpleNamespace(results_summary="1 resultado", active_filters_summary="Sin filtros")

        with patch.object(window, "_load_catalog_snapshot_rows", return_value=snapshot_rows), patch(
            "pos_uniformes.ui.main_window.filter_visible_catalog_rows",
            return_value=snapshot_rows,
        ) as filter_mock, patch(
            "pos_uniformes.ui.main_window.build_catalog_table_row_views",
            return_value=[],
        ), patch(
            "pos_uniformes.ui.main_window.build_catalog_summary_view",
            return_value=summary_view,
        ):
            window._refresh_catalog()

        self.assertTrue(window.catalog_status_filter_combo.isHidden())
        self.assertEqual(filter_mock.call_args.kwargs["filters"].status_filter, "active")

    def test_remove_catalog_multi_filter_chip_keeps_other_selected_values(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_page_index = 3
        window._handle_catalog_filters_changed = Mock()
        window.catalog_type_filter_combo.set_items(
            [
                ("Deportivo", "Deportivo"),
                ("Oficial", "Oficial"),
            ]
        )
        window.catalog_type_filter_combo.set_selected_values(["Deportivo", "Oficial"])

        window._handle_remove_catalog_filter_token(
            ActiveFilterToken(
                key="linea",
                display_text="Linea: Deportivo",
                value="Deportivo",
            )
        )

        self.assertEqual(window.catalog_type_filter_combo.selected_values(), {"Oficial"})
        self.assertEqual(window.catalog_page_index, 0)

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

    def test_clear_inventory_filters_batches_refresh_into_single_pass(self) -> None:
        window = MainWindow(user_id=1)
        window.inventory_search_input.setText("pants")
        window.inventory_brand_filter_combo.set_items([("Marca Norte", "Marca Norte")])
        window.inventory_school_filter_combo.set_items([("General", "General")])
        window.inventory_type_filter_combo.set_items([("Deportivo", "Deportivo")])
        window.inventory_brand_filter_combo.set_selected_values(["Marca Norte"])
        window.inventory_school_filter_combo.set_selected_values(["General"])
        window.inventory_type_filter_combo.set_selected_values(["Deportivo"])
        window.inventory_use_filter_combo.addItem("Solo escolar", "school_only")
        window.inventory_use_filter_combo.setCurrentIndex(window.inventory_use_filter_combo.count() - 1)
        window._run_inventory_filter_refresh = Mock()

        window._handle_clear_inventory_filters()

        self.assertEqual(window._run_inventory_filter_refresh.call_count, 1)
        self.assertEqual(window.inventory_search_input.text(), "")
        self.assertEqual(window.inventory_brand_filter_combo.selected_values(), set())
        self.assertEqual(window.inventory_school_filter_combo.selected_values(), set())
        self.assertEqual(window.inventory_type_filter_combo.selected_values(), set())
        self.assertEqual(window.inventory_use_filter_combo.currentIndex(), 0)

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
