"""Tests de la confirmación de etiquetas al agregar desde búsqueda (Ctrl+S).

Espejo del flujo de caja en Venta Rápida del satélite: al cerrar la búsqueda
con piezas agregadas se ofrece imprimir sus etiquetas (checkboxes, Enter
imprime) usando la tubería de etiquetas del satélite (cache + Brother QL).
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.ui.dialogs.label_print_confirmation_dialog import build_label_entries


_ROWS = {
    "SKU-1": {"producto_nombre_base": "Pants 2pz Deportivo", "talla": "6"},
    "SKU-2": {"producto_nombre_base": "Playera Deportiva", "talla": "CH"},
}


class BuildLabelEntriesTests(unittest.TestCase):
    def test_formats_sku_name_and_size(self) -> None:
        entries = build_label_entries(["SKU-1", "SKU-2"], _ROWS.get)
        self.assertEqual(
            entries,
            [
                ("SKU-1", "SKU-1 · Pants 2pz Deportivo · T:6"),
                ("SKU-2", "SKU-2 · Playera Deportiva · T:CH"),
            ],
        )

    def test_deduplicates_and_normalizes(self) -> None:
        entries = build_label_entries(["sku-1", "SKU-1", "", "SKU-1"], _ROWS.get)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], "SKU-1")

    def test_unknown_sku_falls_back_to_plain_sku(self) -> None:
        entries = build_label_entries(["SKU-9"], _ROWS.get)
        self.assertEqual(entries, [("SKU-9", "SKU-9")])


class SatelliteLabelPrintFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _make_window(self):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        return QuoteSatelliteWindow(user_id=1)

    def test_offer_prints_selected_skus(self) -> None:
        window = self._make_window()
        window._find_row_by_sku = _ROWS.get
        window._print_labels_for_skus = Mock()
        with patch(
            "pos_uniformes.ui.dialogs.label_print_confirmation_dialog.open_label_print_confirmation",
            return_value=["SKU-1"],
        ):
            window._offer_label_print_for_added_skus(["SKU-1", "SKU-2"])
        window._print_labels_for_skus.assert_called_once_with(["SKU-1"])

    def test_offer_skips_print_when_nothing_selected(self) -> None:
        window = self._make_window()
        window._find_row_by_sku = _ROWS.get
        window._print_labels_for_skus = Mock()
        with patch(
            "pos_uniformes.ui.dialogs.label_print_confirmation_dialog.open_label_print_confirmation",
            return_value=[],
        ):
            window._offer_label_print_for_added_skus(["SKU-1"])
        window._print_labels_for_skus.assert_not_called()

    def test_print_labels_renders_and_prints_each_sku(self) -> None:
        window = self._make_window()
        window._find_row_by_sku = _ROWS.get
        window._print_satellite_label = Mock(return_value=True)
        render_result = SimpleNamespace(image_path="/tmp/etiqueta.png")
        with patch(
            "pos_uniformes.services.inventory_label_service.render_inventory_label_from_cache_row",
            return_value=render_result,
        ) as render:
            window._print_labels_for_skus(["SKU-1", "SKU-2"])
        self.assertEqual(render.call_count, 2)
        self.assertEqual(window._print_satellite_label.call_count, 2)
        # Etiqueta normal → paper_mode "standard" para que salga a la impresora
        # "Normal/Split" del menú admin (no la troquelada).
        self.assertEqual(
            window._print_satellite_label.call_args.kwargs["paper_mode"], "standard"
        )

    def test_print_labels_reports_failures_without_aborting(self) -> None:
        window = self._make_window()
        window._find_row_by_sku = _ROWS.get
        window._print_satellite_label = Mock(side_effect=[False, True])
        render_result = SimpleNamespace(image_path="/tmp/etiqueta.png")
        with patch(
            "pos_uniformes.services.inventory_label_service.render_inventory_label_from_cache_row",
            return_value=render_result,
        ), patch(
            "pos_uniformes.ui.quote_satellite_window.QMessageBox.warning"
        ) as warn:
            window._print_labels_for_skus(["SKU-1", "SKU-2"])
        self.assertEqual(window._print_satellite_label.call_count, 2)
        warn.assert_called_once()
        self.assertIn("SKU-1", warn.call_args.args[2])

    def test_quick_search_tracks_added_skus_and_offers_labels(self) -> None:
        window = self._make_window()
        window.current_page_key = "quicksale"
        window.quick_sale_widget = SimpleNamespace(
            add_sku=Mock(return_value=True), focus_input=Mock()
        )
        window._offer_label_print_for_added_skus = Mock()

        class _FakeDialog:
            def __init__(self, *args, **kwargs):
                self._handler = None
                self.sku_selected = SimpleNamespace(connect=self._connect)

            def _connect(self, handler):
                self._handler = handler

            def exec(self):
                self._handler("SKU-1", 1)
                self._handler("SKU-2", 2)
                return 0

        with patch(
            "pos_uniformes.ui.dialogs.quick_product_search_dialog.QuickProductSearchDialog",
            _FakeDialog,
        ):
            window._handle_quick_search()

        window._offer_label_print_for_added_skus.assert_called_once_with(["SKU-1", "SKU-2"])
        window.quick_sale_widget.focus_input.assert_called_once()


if __name__ == "__main__":
    unittest.main()
