from __future__ import annotations

import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget


def _snap(sku: str, name: str = "Pants", price: str = "515.00"):
    return SimpleNamespace(
        sku=sku,
        product_name=name,
        size_label="6",
        color_label="",
        price=Decimal(price),
    )


class QuickSaleAddSkuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _make_widget(self) -> QuickSaleWidget:
        satellite = SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None)
        widget = QuickSaleWidget(satellite)
        return widget

    def test_add_sku_requires_employee_gate(self) -> None:
        widget = self._make_widget()
        with patch.object(QuickSaleWidget, "_refresh_items_table"), patch(
            "pos_uniformes.ui.views.quick_sale_view.QMessageBox.warning"
        ) as warn:
            added = widget.add_sku("SKU004838", 1)
        self.assertFalse(added)
        self.assertEqual(widget._items, [])
        warn.assert_called_once()

    def test_add_sku_adds_new_item(self) -> None:
        widget = self._make_widget()
        widget._employee_code = "VEND-1"
        widget.satellite._kiosk_lookup_from_cache = lambda sku: _snap(sku)
        with patch.object(QuickSaleWidget, "_refresh_items_table"), patch.object(
            QuickSaleWidget, "_refresh_totals"
        ):
            added = widget.add_sku("sku004838", 2)
        self.assertTrue(added)
        self.assertEqual(len(widget._items), 1)
        self.assertEqual(widget._items[0]["sku"], "SKU004838")
        self.assertEqual(widget._items[0]["cantidad"], 2)

    def test_add_sku_accumulates_quantity(self) -> None:
        widget = self._make_widget()
        widget._employee_code = "VEND-1"
        widget.satellite._kiosk_lookup_from_cache = lambda sku: _snap("SKU004838")
        with patch.object(QuickSaleWidget, "_refresh_items_table"), patch.object(
            QuickSaleWidget, "_refresh_totals"
        ):
            widget.add_sku("SKU004838", 1)
            widget.add_sku("SKU004838", 3)
        self.assertEqual(len(widget._items), 1)
        self.assertEqual(widget._items[0]["cantidad"], 4)

    def test_add_sku_unknown_shows_warning(self) -> None:
        widget = self._make_widget()
        widget._employee_code = "VEND-1"

        def _raise(sku):
            raise ValueError("No existe")

        widget.satellite._kiosk_lookup_from_cache = _raise
        with patch.object(QuickSaleWidget, "_refresh_items_table"), patch(
            "pos_uniformes.ui.views.quick_sale_view.QMessageBox.warning"
        ) as warn:
            added = widget.add_sku("NOPE", 1)
        self.assertFalse(added)
        self.assertEqual(widget._items, [])
        warn.assert_called_once()


class ApartadoTicketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _make_widget(self) -> QuickSaleWidget:
        satellite = SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None)
        widget = QuickSaleWidget(satellite)
        widget._employee_code = "VEND-1"
        widget._employee_name = "Daniel Fabian"
        widget._items = [
            {"sku": "SKU004838", "nombre": "Pants", "talla": "6", "color": "",
             "precio": Decimal("500.00"), "cantidad": 1},
        ]
        return widget

    def test_client_copy_includes_terms(self) -> None:
        widget = self._make_widget()
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")):
            text = widget._build_apartado_text("Ana", copy_label="CLIENTE", include_terms=True)
        self.assertIn("Terminos y Condiciones", text)
        self.assertIn("- CLIENTE -", text)

    def test_store_copy_excludes_terms(self) -> None:
        widget = self._make_widget()
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")):
            text = widget._build_apartado_text("Ana", copy_label="COPIA TIENDA", include_terms=False)
        self.assertNotIn("Terminos y Condiciones", text)
        self.assertIn("- COPIA TIENDA -", text)

    def test_both_copies_show_minimum_20pct(self) -> None:
        widget = self._make_widget()
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")):
            text = widget._build_apartado_text("Ana", include_terms=True)
        # 20% de 500 = 100.00
        self.assertIn("Apartado minimo (20%):", text)
        self.assertIn("$100.00", text)


if __name__ == "__main__":
    unittest.main()
