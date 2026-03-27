from __future__ import annotations

import unittest
from unittest.mock import Mock

from pos_uniformes.ui.helpers.inventory_filter_helper import (
    InventoryVisibleFilterState,
    filter_visible_inventory_rows,
    inventory_row_matches_visible_filters,
)


class InventoryFilterHelperTests(unittest.TestCase):
    def test_inventory_row_matches_visible_filters_accepts_matching_row(self) -> None:
        row = {
            "categoria_nombre": "Uniforme",
            "marca_nombre": "Marca Norte",
            "escuela_nombre": "General",
            "tipo_prenda_nombre": "Deportivo",
            "tipo_pieza_nombre": "Pants",
            "talla": "16",
            "color": "Azul",
            "variante_activa": True,
            "stock_actual": 5,
            "qr_exists": True,
            "origen_legacy": False,
            "fallback_importacion": False,
        }

        matches = inventory_row_matches_visible_filters(
            row,
            filters=InventoryVisibleFilterState(
                search_text="sku",
                category_filters=("Uniforme",),
                brand_filters=("Marca Norte",),
                school_filters=("General",),
                type_filters=("Deportivo",),
                piece_filters=("Pants",),
                size_filters=("16",),
                color_filters=("Azul",),
                status_filter="active",
                stock_filter="available",
                qr_filter="ready",
                origin_filter="native",
                duplicate_filter="fallback_exclude",
            ),
            search_matcher=lambda _row, search_text: search_text == "sku",
        )

        self.assertTrue(matches)

    def test_inventory_row_matches_visible_filters_rejects_missing_qr(self) -> None:
        row = {
            "categoria_nombre": "Uniforme",
            "marca_nombre": "Marca Norte",
            "escuela_nombre": "General",
            "tipo_prenda_nombre": "Deportivo",
            "tipo_pieza_nombre": "Pants",
            "talla": "16",
            "color": "Azul",
            "variante_activa": True,
            "stock_actual": 5,
            "qr_exists": False,
            "origen_legacy": False,
            "fallback_importacion": False,
        }

        matches = inventory_row_matches_visible_filters(
            row,
            filters=InventoryVisibleFilterState(
                search_text="",
                category_filters=(),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="",
                stock_filter="",
                qr_filter="ready",
                origin_filter="",
                duplicate_filter="",
            ),
            search_matcher=lambda *_args: True,
        )

        self.assertFalse(matches)

    def test_filter_visible_inventory_rows_keeps_only_matching_rows(self) -> None:
        rows = [
            {
                "sku": "SKU-001",
                "categoria_nombre": "Uniforme",
                "marca_nombre": "Marca Norte",
                "escuela_nombre": "General",
                "tipo_prenda_nombre": "Deportivo",
                "tipo_pieza_nombre": "Pants",
                "talla": "16",
                "color": "Azul",
                "variante_activa": True,
                "stock_actual": 5,
                "qr_exists": True,
                "origen_legacy": False,
                "fallback_importacion": False,
            },
            {
                "sku": "SKU-002",
                "categoria_nombre": "Uniforme",
                "marca_nombre": "Marca Norte",
                "escuela_nombre": "General",
                "tipo_prenda_nombre": "Oficial",
                "tipo_pieza_nombre": "Camisa",
                "talla": "14",
                "color": "Blanco",
                "variante_activa": False,
                "stock_actual": 0,
                "qr_exists": False,
                "origen_legacy": True,
                "fallback_importacion": True,
            },
        ]

        visible_rows = filter_visible_inventory_rows(
            rows,
            filters=InventoryVisibleFilterState(
                search_text="sku-001",
                category_filters=(),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="active",
                stock_filter="available",
                qr_filter="ready",
                origin_filter="native",
                duplicate_filter="fallback_exclude",
            ),
            search_matcher=lambda row, search_text: str(row["sku"]).lower() == search_text,
        )

        self.assertEqual([row["sku"] for row in visible_rows], ["SKU-001"])

    def test_inventory_row_matches_visible_filters_skips_search_matcher_when_exact_filter_already_fails(self) -> None:
        row = {
            "categoria_nombre": "Uniforme",
            "marca_nombre": "Marca Norte",
            "escuela_nombre": "General",
            "tipo_prenda_nombre": "Deportivo",
            "tipo_pieza_nombre": "Pants",
            "talla": "16",
            "color": "Azul",
            "variante_activa": True,
            "stock_actual": 5,
            "qr_exists": True,
            "origen_legacy": False,
            "fallback_importacion": False,
        }
        search_matcher = Mock(return_value=True)

        matches = inventory_row_matches_visible_filters(
            row,
            filters=InventoryVisibleFilterState(
                search_text="sku",
                category_filters=("Calzado",),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="",
                stock_filter="",
                qr_filter="",
                origin_filter="",
                duplicate_filter="",
            ),
            search_matcher=search_matcher,
        )

        self.assertFalse(matches)
        search_matcher.assert_not_called()


if __name__ == "__main__":
    unittest.main()
