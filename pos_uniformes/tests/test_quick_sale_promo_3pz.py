"""Tests de la promo 3pz (pants 2pz + playera) en Venta Rápida del satélite.

Espejo del flujo de caja: al agregar un pants 2pz deportivo se ofrece la
playera de la misma escuela a $100; si se quita el pants, la playera regresa
a su precio original.
"""

from __future__ import annotations

import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.helpers.quick_sale_sports_uniform_helper import (
    adapt_cache_row,
    build_promo_playera_item,
    load_playera_candidates_from_rows,
    mark_promo_base_item,
    restore_promo_playera_after_base_removed,
)
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import (
    SaleSportsUniformResolution,
    is_deportivo_playera_variant,
    is_deportivo_two_piece_variant,
)
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget


def _row(
    sku: str,
    producto: str,
    *,
    escuela: str = "Colegio Mexico",
    talla: str = "6",
    precio: str = "150.00",
    activo: bool = True,
) -> dict:
    return {
        "sku": sku,
        "producto_nombre": producto,
        "producto_nombre_base": producto,
        "producto_descripcion": "",
        "escuela_nombre": escuela,
        "tipo_prenda_nombre": "",
        "tipo_pieza_nombre": "",
        "talla": talla,
        "color": "Rojo",
        "precio_venta": precio,
        "producto_activo": activo,
        "variante_activo": activo,
    }


_PANTS_ROW = _row("P2-001", "Pants 2pz Deportivo", precio="450.00")
_PLAYERA_ROW = _row("PLY-001", "Playera Deportiva", precio="150.00")


class AdapterDetectionTests(unittest.TestCase):
    def test_pants_2pz_deportivo_is_detected(self) -> None:
        self.assertTrue(is_deportivo_two_piece_variant(adapt_cache_row(_PANTS_ROW)))

    def test_playera_deportiva_is_detected(self) -> None:
        self.assertTrue(is_deportivo_playera_variant(adapt_cache_row(_PLAYERA_ROW)))

    def test_regular_garment_is_not_detected(self) -> None:
        camisa = adapt_cache_row(_row("C-001", "Camisa Escolar Blanca"))
        self.assertFalse(is_deportivo_two_piece_variant(camisa))
        self.assertFalse(is_deportivo_playera_variant(camisa))

    def test_adapt_none_returns_none(self) -> None:
        self.assertIsNone(adapt_cache_row(None))


class PlayeraCandidatesTests(unittest.TestCase):
    def test_filters_same_school_active_playeras(self) -> None:
        base = adapt_cache_row(_PANTS_ROW)
        rows = [
            _PLAYERA_ROW,
            _row("PLY-002", "Playera Deportiva", escuela="Otra Escuela"),
            _row("PLY-003", "Playera Deportiva", activo=False),
            _row("F-001", "Falda Escolar"),
        ]
        candidates = load_playera_candidates_from_rows(rows, base)
        self.assertEqual([c.sku for c in candidates], ["PLY-001"])


class PromoItemTests(unittest.TestCase):
    def test_promo_item_has_special_price_and_metadata(self) -> None:
        item = build_promo_playera_item(adapt_cache_row(_PLAYERA_ROW), base_sku="P2-001")
        self.assertEqual(item["precio"], Decimal("100.00"))
        self.assertEqual(item["precio_base"], Decimal("150.00"))
        self.assertEqual(item["nombre"], "Playera Deportiva (promo 3pz)")
        self.assertEqual(item["sports_uniform_role"], "playera")
        self.assertEqual(item["sports_uniform_base_sku"], "P2-001")

    def test_restore_after_base_removed(self) -> None:
        playera_item = build_promo_playera_item(adapt_cache_row(_PLAYERA_ROW), base_sku="P2-001")
        base_item = {"sku": "P2-001", "nombre": "Pants 2pz Deportivo", "cantidad": 1}
        mark_promo_base_item(base_item, playera_sku="PLY-001")
        items = [playera_item]

        message = restore_promo_playera_after_base_removed(items, base_item)

        self.assertTrue(message)
        self.assertEqual(playera_item["precio"], Decimal("150.00"))
        self.assertEqual(playera_item["nombre"], "Playera Deportiva")
        self.assertNotIn("sports_uniform_role", playera_item)

    def test_restore_ignores_non_base_removals(self) -> None:
        playera_item = build_promo_playera_item(adapt_cache_row(_PLAYERA_ROW), base_sku="P2-001")
        message = restore_promo_playera_after_base_removed(
            [playera_item], {"sku": "X", "nombre": "Otra cosa"}
        )
        self.assertEqual(message, "")
        self.assertEqual(playera_item["precio"], Decimal("100.00"))


def _snap(sku: str, name: str, price: str) -> SimpleNamespace:
    return SimpleNamespace(
        sku=sku, product_name=name, size_label="6", color_label="Rojo", price=Decimal(price)
    )


class QuickSalePromoFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _make_widget(self) -> QuickSaleWidget:
        rows = {"P2-001": _PANTS_ROW, "PLY-001": _PLAYERA_ROW}
        satellite = SimpleNamespace(
            offline_mode=True,
            _kiosk_lookup_from_cache=lambda sku: _snap(
                sku, rows[sku]["producto_nombre"], str(rows[sku]["precio_venta"])
            ),
            _find_row_by_sku=lambda sku: rows.get(sku),
            catalog_snapshot_rows=list(rows.values()),
        )
        widget = QuickSaleWidget(satellite)
        widget._employee_code = "VEND-2"
        widget._employee_name = "Ana"
        return widget

    def test_composed_resolution_adds_playera_at_promo_price(self) -> None:
        widget = self._make_widget()
        resolution = SaleSportsUniformResolution(
            variants=(adapt_cache_row(_PANTS_ROW), adapt_cache_row(_PLAYERA_ROW)),
            composed_as_three_pieces=True,
            selected_playera_sku="PLY-001",
        )
        with patch(
            "pos_uniformes.ui.views.quick_sale_view.resolve_sale_scan_variants",
            return_value=resolution,
        ), patch.object(QuickSaleWidget, "_refresh_items_table"), patch.object(
            QuickSaleWidget, "_refresh_totals"
        ):
            added = widget.add_sku("P2-001", 1)

        self.assertTrue(added)
        self.assertEqual(len(widget._items), 2)
        pants, playera = widget._items
        self.assertEqual(pants["sports_uniform_role"], "base")
        self.assertEqual(pants["sports_uniform_playera_sku"], "PLY-001")
        self.assertEqual(playera["precio"], Decimal("100.00"))
        self.assertEqual(playera["sports_uniform_role"], "playera")

    def test_cancelled_resolution_aborts_add(self) -> None:
        widget = self._make_widget()
        with patch(
            "pos_uniformes.ui.views.quick_sale_view.resolve_sale_scan_variants",
            return_value=None,
        ), patch.object(QuickSaleWidget, "_refresh_items_table"):
            added = widget.add_sku("P2-001", 1)
        self.assertFalse(added)
        self.assertEqual(widget._items, [])

    def test_pants_only_resolution_adds_single_line(self) -> None:
        widget = self._make_widget()
        resolution = SaleSportsUniformResolution(variants=(adapt_cache_row(_PANTS_ROW),))
        with patch(
            "pos_uniformes.ui.views.quick_sale_view.resolve_sale_scan_variants",
            return_value=resolution,
        ), patch.object(QuickSaleWidget, "_refresh_items_table"), patch.object(
            QuickSaleWidget, "_refresh_totals"
        ):
            added = widget.add_sku("P2-001", 1)
        self.assertTrue(added)
        self.assertEqual(len(widget._items), 1)
        self.assertNotIn("sports_uniform_role", widget._items[0])

    def test_non_deportivo_sku_skips_promo_flow(self) -> None:
        widget = self._make_widget()
        rows = {"C-001": _row("C-001", "Camisa Escolar Blanca")}
        widget.satellite._find_row_by_sku = lambda sku: rows.get(sku)
        widget.satellite._kiosk_lookup_from_cache = lambda sku: _snap(sku, "Camisa Escolar Blanca", "150.00")
        with patch(
            "pos_uniformes.ui.views.quick_sale_view.resolve_sale_scan_variants"
        ) as resolve, patch.object(QuickSaleWidget, "_refresh_items_table"), patch.object(
            QuickSaleWidget, "_refresh_totals"
        ):
            added = widget.add_sku("C-001", 1)
        self.assertTrue(added)
        resolve.assert_not_called()

    def test_removing_base_restores_playera_price(self) -> None:
        widget = self._make_widget()
        playera_item = build_promo_playera_item(adapt_cache_row(_PLAYERA_ROW), base_sku="P2-001")
        base_item = {
            "sku": "P2-001", "nombre": "Pants 2pz Deportivo", "talla": "6",
            "color": "Rojo", "precio": Decimal("450.00"), "cantidad": 1,
        }
        mark_promo_base_item(base_item, playera_sku="PLY-001")
        widget._items = [base_item, playera_item]

        with patch.object(QuickSaleWidget, "_refresh_items_table"), patch.object(
            QuickSaleWidget, "_refresh_totals"
        ), patch("pos_uniformes.ui.views.quick_sale_view.QMessageBox.information"):
            widget._on_remove(0)

        self.assertEqual(len(widget._items), 1)
        self.assertEqual(widget._items[0]["precio"], Decimal("150.00"))
        self.assertEqual(widget._items[0]["nombre"], "Playera Deportiva")


if __name__ == "__main__":
    unittest.main()
