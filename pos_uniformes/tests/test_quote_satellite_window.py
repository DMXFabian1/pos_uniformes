from __future__ import annotations

import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from pos_uniformes.services.active_filter_service import ActiveFilterToken
from pos_uniformes.ui.helpers.flow_layout import FlowLayout
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

    def test_catalog_defaults_to_solo_escuela_mode(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)

        self.assertEqual(window.catalog_include_general_combo.currentData(), "school_only")
        self.assertEqual(window.catalog_include_general_combo.currentText(), "Solo escuela")

    def test_catalog_status_label_is_not_shown_in_browser_layout(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        catalog_page = window.page_stack.widget(1)
        browser_box = catalog_page.layout().itemAt(0).widget()
        browser_layout = browser_box.layout()

        self.assertEqual(browser_layout.indexOf(window.catalog_status_label), -1)
        self.assertFalse(window.catalog_status_label.isVisible())

    def test_catalog_table_keeps_header_row_visible(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)

        self.assertFalse(window.catalog_table.horizontalHeader().isHidden())

    def test_catalog_active_filter_chips_show_text_and_route(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        window.catalog_search_input.blockSignals(True)
        window.catalog_search_input.setText("pants")
        window.catalog_search_input.blockSignals(False)

        window._refresh_catalog_active_filter_chips()

        layout = window.catalog_active_filters_flow_layout
        texts = [layout.itemAt(index).widget().text() for index in range(layout.count())]
        self.assertFalse(window.catalog_active_filters_wrap.isHidden())
        self.assertEqual(
            texts,
            ['Texto: "pants"  ×', "Ruta: Solo escuela  ×"],
        )

    def test_remove_catalog_route_filter_token_resets_to_include_general(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)

        window._handle_remove_catalog_filter_token(
            ActiveFilterToken(
                key="ruta",
                display_text="Ruta: Solo escuela",
                value="Solo escuela",
            )
        )

        self.assertEqual(window.catalog_include_general_combo.currentData(), "include_general")
        window._refresh_catalog_active_filter_chips()
        texts = [
            window.catalog_active_filters_flow_layout.itemAt(index).widget().text()
            for index in range(window.catalog_active_filters_flow_layout.count())
        ]
        self.assertNotIn("Ruta: Escuela + extras generales  ×", texts)

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

    def test_stylesheet_includes_combo_hover_feedback(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)

        self.assertIn("QComboBox QAbstractItemView::item:hover", window.styleSheet())
        self.assertIn("QPushButton#secondaryButton:hover", window.styleSheet())
        self.assertIn("QPushButton#navButton:hover", window.styleSheet())
        self.assertIn("QComboBox:hover", window.styleSheet())
        self.assertIn("#a9c1d6", window.styleSheet())
        self.assertIn("QComboBox#satFilterCombo:hover", window.styleSheet())
        self.assertIn("QPushButton#chipButton[active=\"true\"]", window.styleSheet())
        self.assertIn("background: #fbf8f2;", window.styleSheet())
        self.assertIn("background: #f2ece3;", window.styleSheet())
        self.assertIn("background: #efe4d5;", window.styleSheet())

    def test_quote_cart_uses_six_columns_and_cashier_style(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)

        self.assertEqual(window.quote_cart_table.columnCount(), 6)
        self.assertEqual(window.quote_cart_table.objectName(), "cashierCartTable")
        self.assertEqual(window.quote_cart_table.horizontalHeaderItem(0).text(), "Cantidad")
        self.assertEqual(window.quote_cart_table.horizontalHeaderItem(1).text(), "Producto")

    def test_window_title_and_version_show_kiosk_build_identity(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)

        self.assertIn("Kiosko de Presupuestos", window.windowTitle())
        self.assertTrue(window.version_label.text().startswith("Version "))

    def test_grouped_kiosk_product_cards_use_compact_layout(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        window.guided_mode = "basics"
        window.guided_selected_piece = "Bata"
        window.catalog_snapshot_rows = [
            {
                "sku": "SKU000179",
                "producto_nombre_base": "Bata Infantil Amarillo",
                "tipo_pieza_nombre": "Bata",
            }
        ]

        card = SimpleNamespace(
            key="Bata||Bata Infantil Amarillo",
            sku="SKU000179",
            title="Bata Infantil Amarillo",
            subtitle="Tallas: Uni",
            price_label="$65.00",
        )

        button = window._build_guided_product_button(card)

        self.assertTrue(button.property("compactCard"))
        self.assertNotIn("$65.00", button.text())
        self.assertEqual(button.minimumHeight(), 68)
        self.assertEqual(button.minimumWidth(), 252)
        self.assertEqual(button.maximumWidth(), 252)
        self.assertEqual(button.sizePolicy().horizontalPolicy(), button.sizePolicy().Policy.Fixed)

    def test_school_guided_product_cards_use_same_compact_layout(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        window.guided_mode = "school"
        window.guided_selected_school = "Colegio Mexico"
        window.catalog_snapshot_rows = [
            {
                "sku": "SKU000200",
                "producto_nombre_base": "Falda Escolar Tabla",
                "tipo_pieza_nombre": "Falda",
            }
        ]

        card = SimpleNamespace(
            key="Falda||Falda Escolar Tabla",
            sku="SKU000200",
            title="Falda Escolar Tabla",
            subtitle="Tallas: 10, 12",
            price_label="$199.00",
        )

        button = window._build_guided_product_button(card)

        self.assertTrue(button.property("compactCard"))
        self.assertEqual(button.minimumHeight(), 68)
        self.assertEqual(button.minimumWidth(), 252)
        self.assertEqual(button.maximumWidth(), 252)
        self.assertEqual(button.sizePolicy().horizontalPolicy(), button.sizePolicy().Policy.Fixed)

    def test_guided_piece_buttons_use_compact_symmetric_grid(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)

        options = [
            SimpleNamespace(key="Camisa", label="Camisa", enabled=True, group_label="Prendas principales"),
            SimpleNamespace(key="Playera", label="Playera", enabled=True, group_label="Prendas principales"),
            SimpleNamespace(key="Calceta", label="Calceta", enabled=True, group_label="Accesorios"),
            SimpleNamespace(key="Corbata", label="Corbata", enabled=True, group_label="Accesorios"),
            SimpleNamespace(key="Bata", label="Bata", enabled=True, group_label="Especial"),
        ]

        window._rebuild_guided_piece_buttons(options)

        first_button = window.guided_piece_buttons["Camisa"]
        self.assertTrue(first_button.property("compactChoice"))
        self.assertEqual(first_button.minimumHeight(), 42)
        self.assertEqual(first_button.maximumWidth(), 170)
        self.assertEqual(window.guided_piece_groups_layout.count(), 6)

    def test_guided_product_cards_use_flow_layout(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        window.guided_mode = "basics"
        window.guided_selected_piece = "Camisa"
        cards = [
            SimpleNamespace(key="a", sku="SKU1", title="Camisa Azul", subtitle="5 tallas disponibles", price_label="$139.00"),
            SimpleNamespace(key="b", sku="SKU2", title="Camisa Blanca", subtitle="11 tallas disponibles", price_label="$139.00"),
        ]

        window._rebuild_guided_product_buttons(cards)

        self.assertIsInstance(window.guided_product_flow_layout, FlowLayout)
        self.assertEqual(window.guided_product_flow_layout.count(), 2)

    def test_guided_variant_buttons_use_flow_layout_and_compact_size(self) -> None:
        window = QuoteSatelliteWindow(user_id=1)
        options = [
            SimpleNamespace(sku="SKU-1", label="Talla 10 · $239.00", price_label="$239.00"),
            SimpleNamespace(sku="SKU-2", label="Talla 12 · $239.00", price_label="$239.00"),
            SimpleNamespace(sku="SKU-3", label="Talla 14 · $259.00", price_label="$259.00"),
        ]

        window._rebuild_guided_variant_buttons(options)

        first_button = window.guided_variant_buttons["SKU-1"]
        first_group = window.guided_variant_groups_layout.itemAt(0).layout()
        second_group = window.guided_variant_groups_layout.itemAt(1).layout()
        self.assertIsInstance(first_group, FlowLayout)
        self.assertIsInstance(second_group, FlowLayout)
        self.assertTrue(first_button.property("compactChoice"))
        self.assertEqual(first_button.minimumHeight(), 42)
        self.assertEqual(window.guided_variant_groups_layout.count(), 2)


if __name__ == "__main__":
    unittest.main()
