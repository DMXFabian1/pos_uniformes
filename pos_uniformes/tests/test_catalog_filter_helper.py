from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_filter_helper import (
    CatalogVisibleFilterState,
    catalog_row_matches_visible_filters,
    filter_visible_catalog_rows,
)


class CatalogFilterHelperTests(unittest.TestCase):
    def test_catalog_row_matches_visible_filters_accepts_matching_row(self) -> None:
        row = {
            "categoria_nombre": "Uniforme",
            "marca_nombre": "Marca Norte",
            "escuela_nombre": "General",
            "tipo_prenda_nombre": "Deportivo",
            "tipo_pieza_nombre": "Pants",
            "talla": "16",
            "color": "Azul",
            "variante_activo": True,
            "stock_actual": 5,
            "apartado_cantidad": 1,
            "origen_legacy": False,
            "fallback_importacion": False,
        }

        matches = catalog_row_matches_visible_filters(
            row,
            filters=CatalogVisibleFilterState(
                search_text="pants",
                school_scope_filter="",
                category_filters=("Uniforme",),
                brand_filters=("Marca Norte",),
                school_filters=("General",),
                type_filters=("Deportivo",),
                piece_filters=("Pants",),
                size_filters=("16",),
                color_filters=("Azul",),
                status_filter="active",
                stock_filter="in_stock",
                layaway_filter="reserved",
                origin_filter="native",
                duplicate_filter="fallback_exclude",
            ),
            search_matcher=lambda _row, search_text: search_text == "pants",
        )

        self.assertTrue(matches)

    def test_catalog_row_matches_visible_filters_rejects_non_matching_stock_rule(self) -> None:
        row = {
            "categoria_nombre": "Uniforme",
            "marca_nombre": "Marca Norte",
            "escuela_nombre": "General",
            "tipo_prenda_nombre": "Deportivo",
            "tipo_pieza_nombre": "Pants",
            "talla": "16",
            "color": "Azul",
            "variante_activo": True,
            "stock_actual": 1,
            "apartado_cantidad": 2,
            "origen_legacy": False,
            "fallback_importacion": False,
        }

        matches = catalog_row_matches_visible_filters(
            row,
            filters=CatalogVisibleFilterState(
                search_text="",
                school_scope_filter="",
                category_filters=(),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="",
                stock_filter="available_over_reserved",
                layaway_filter="",
                origin_filter="",
                duplicate_filter="",
            ),
            search_matcher=lambda *_args: True,
        )

        self.assertFalse(matches)

    def test_filter_visible_catalog_rows_keeps_only_matching_rows(self) -> None:
        rows = [
            {
                "categoria_nombre": "Uniforme",
                "marca_nombre": "Marca Norte",
                "escuela_nombre": "General",
                "tipo_prenda_nombre": "Deportivo",
                "tipo_pieza_nombre": "Pants",
                "talla": "16",
                "color": "Azul",
                "variante_activo": True,
                "stock_actual": 5,
                "apartado_cantidad": 1,
                "origen_legacy": False,
                "fallback_importacion": False,
                "sku": "SKU-001",
            },
            {
                "categoria_nombre": "Uniforme",
                "marca_nombre": "Marca Norte",
                "escuela_nombre": "General",
                "tipo_prenda_nombre": "Oficial",
                "tipo_pieza_nombre": "Camisa",
                "talla": "14",
                "color": "Blanco",
                "variante_activo": False,
                "stock_actual": 0,
                "apartado_cantidad": 0,
                "origen_legacy": True,
                "fallback_importacion": True,
                "sku": "SKU-002",
            },
        ]

        visible_rows = filter_visible_catalog_rows(
            rows,
            filters=CatalogVisibleFilterState(
                search_text="sku-001",
                school_scope_filter="",
                category_filters=(),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="active",
                stock_filter="in_stock",
                layaway_filter="",
                origin_filter="native",
                duplicate_filter="fallback_exclude",
            ),
            search_matcher=lambda row, search_text: str(row["sku"]).lower() == search_text,
        )

        self.assertEqual([row["sku"] for row in visible_rows], ["SKU-001"])

    def test_catalog_row_matches_visible_filters_supports_general_only_scope_for_non_uniform_category(self) -> None:
        row = {
            "categoria_nombre": "Ropa casual",
            "marca_nombre": "Marca Norte",
            "escuela_nombre": "General",
            "tipo_prenda_nombre": "Casual",
            "tipo_pieza_nombre": "Playera",
            "talla": "M",
            "color": "Negro",
            "variante_activo": True,
            "stock_actual": 5,
            "apartado_cantidad": 0,
            "origen_legacy": False,
            "fallback_importacion": False,
        }

        matches = catalog_row_matches_visible_filters(
            row,
            filters=CatalogVisibleFilterState(
                search_text="",
                school_scope_filter="general_only",
                category_filters=(),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="",
                stock_filter="",
                layaway_filter="",
                origin_filter="",
                duplicate_filter="",
            ),
            search_matcher=lambda *_args: True,
        )

        self.assertTrue(matches)

    def test_catalog_row_matches_visible_filters_rejects_uniform_category_for_general_only_scope(self) -> None:
        row = {
            "categoria_nombre": "Básico",
            "marca_nombre": "Marca Norte",
            "escuela_nombre": "General",
            "tipo_prenda_nombre": "Básico",
            "tipo_pieza_nombre": "Playera",
            "talla": "M",
            "color": "Negro",
            "variante_activo": True,
            "stock_actual": 5,
            "apartado_cantidad": 0,
            "origen_legacy": False,
            "fallback_importacion": False,
        }

        matches = catalog_row_matches_visible_filters(
            row,
            filters=CatalogVisibleFilterState(
                search_text="",
                school_scope_filter="general_only",
                category_filters=(),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="",
                stock_filter="",
                layaway_filter="",
                origin_filter="",
                duplicate_filter="",
            ),
            search_matcher=lambda *_args: True,
        )

        self.assertFalse(matches)

    def test_catalog_row_matches_visible_filters_accepts_uniform_category_for_school_only_scope(self) -> None:
        row = {
            "categoria_nombre": "Oficial",
            "marca_nombre": "Marca Norte",
            "escuela_nombre": "General",
            "tipo_prenda_nombre": "Oficial",
            "tipo_pieza_nombre": "Camisa",
            "talla": "M",
            "color": "Blanco",
            "variante_activo": True,
            "stock_actual": 5,
            "apartado_cantidad": 0,
            "origen_legacy": False,
            "fallback_importacion": False,
        }

        matches = catalog_row_matches_visible_filters(
            row,
            filters=CatalogVisibleFilterState(
                search_text="",
                school_scope_filter="school_only",
                category_filters=(),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="",
                stock_filter="",
                layaway_filter="",
                origin_filter="",
                duplicate_filter="",
            ),
            search_matcher=lambda *_args: True,
        )

        self.assertTrue(matches)


if __name__ == "__main__":
    unittest.main()
