"""Tests del blindaje de indices del carrito de presupuesto.

Bug original: en el popup "Piezas agregadas" del satelite, los handlers de
−/+/✕ se conectaban como `def _on_remove(index=original_idx)` — la señal
clicked de Qt pasa checked (bool) como primer argumento posicional, asi que
index recibia False (== 0) y siempre se borraba/modificaba la PRIMERA linea
del carrito en vez de la seleccionada.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.ui.helpers.quote_cart_view_helper import normalize_cart_row_index


class NormalizeCartRowIndexTests(unittest.TestCase):
    def test_bool_is_never_a_valid_index(self) -> None:
        # False == 0 y True == 1 en Python: un checked de Qt que se cuela
        # como indice tocaria la fila 0/1 — debe rechazarse siempre.
        self.assertIsNone(normalize_cart_row_index(False, cart_length=3))
        self.assertIsNone(normalize_cart_row_index(True, cart_length=3))

    def test_non_int_is_rejected(self) -> None:
        self.assertIsNone(normalize_cart_row_index("1", cart_length=3))
        self.assertIsNone(normalize_cart_row_index(None, cart_length=3))
        self.assertIsNone(normalize_cart_row_index(1.0, cart_length=3))

    def test_out_of_range_is_rejected(self) -> None:
        self.assertIsNone(normalize_cart_row_index(-1, cart_length=3))
        self.assertIsNone(normalize_cart_row_index(3, cart_length=3))
        self.assertIsNone(normalize_cart_row_index(0, cart_length=0))

    def test_valid_index_passes_through(self) -> None:
        self.assertEqual(normalize_cart_row_index(0, cart_length=3), 0)
        self.assertEqual(normalize_cart_row_index(2, cart_length=3), 2)


class SatelliteCartGuardTests(unittest.TestCase):
    """El blindaje aplicado en la ventana: un bool jamas toca el carrito."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _make_window(self):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        window = QuoteSatelliteWindow(user_id=1)
        window.quote_cart = [
            {"sku": "SKU-A", "producto_nombre": "Playera", "cantidad": 1, "precio_unitario": "100.00"},
            {"sku": "SKU-B", "producto_nombre": "Pants", "cantidad": 2, "precio_unitario": "200.00"},
            {"sku": "SKU-C", "producto_nombre": "Sueter", "cantidad": 3, "precio_unitario": "300.00"},
        ]
        return window

    def test_remove_with_bool_index_is_a_noop(self) -> None:
        window = self._make_window()
        window._remove_quote_item_at_index(False)
        self.assertEqual([i["sku"] for i in window.quote_cart], ["SKU-A", "SKU-B", "SKU-C"])

    def test_remove_with_valid_index_removes_that_row(self) -> None:
        window = self._make_window()
        window._remove_quote_item_at_index(1)
        self.assertEqual([i["sku"] for i in window.quote_cart], ["SKU-A", "SKU-C"])

    def test_change_quantity_with_bool_index_is_a_noop(self) -> None:
        window = self._make_window()
        window.offline_mode = True
        window._change_sidebar_item_quantity(False, 1)
        self.assertEqual(window.quote_cart[0]["cantidad"], 1)

    def test_change_quantity_with_valid_index_changes_that_row(self) -> None:
        window = self._make_window()
        window.offline_mode = True
        window._change_sidebar_item_quantity(2, 1)
        self.assertEqual(window.quote_cart[2]["cantidad"], 4)
        self.assertEqual(window.quote_cart[0]["cantidad"], 1)


if __name__ == "__main__":
    unittest.main()
