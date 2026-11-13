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
            "origen_legacy": False,
            "fallback_importacion": False,
            "ultimo_conteo_at": None,
            "stock_minimo": None,
            "precio_venta": "150.00",
        }

        matches = inventory_row_matches_visible_filters(
            row,
            filters=InventoryVisibleFilterState(
                search_text="sku",
                use_filter="school_only",
                category_filters=("Uniforme",),
                brand_filters=("Marca Norte",),
                school_filters=("General",),
                type_filters=("Deportivo",),
                piece_filters=("Pants",),
                size_filters=("16",),
                color_filters=("Azul",),
                status_filter="active",
                stock_filter="available",
                conteo_filter="",
                precio_filter="",
                precio_text_filter="",
            ),
            search_matcher=lambda _row, search_text: search_text == "sku",
        )

        self.assertTrue(matches)

    def test_fila_sin_dato_de_qr_pasa_porque_ya_no_hay_filtro_qr(self) -> None:
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
            "origen_legacy": False,
            "fallback_importacion": False,
            "ultimo_conteo_at": None,
            "stock_minimo": None,
            "precio_venta": "150.00",
        }

        matches = inventory_row_matches_visible_filters(
            row,
            filters=InventoryVisibleFilterState(
                search_text="",
                use_filter="",
                category_filters=(),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="",
                stock_filter="",
                conteo_filter="",
                precio_filter="",
                precio_text_filter="",
            ),
            search_matcher=lambda *_args: True,
        )

        self.assertTrue(matches)

    def test_filtros_de_precio_usan_el_precio_rebajado_que_dice_la_columna(self) -> None:
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
            "precio_venta": "250.00",
            "rebaja_tipo": "oferta",
            "rebaja_precio": "175.00",
        }

        def filtros(precio_filter: str = "", precio_text_filter: str = "") -> InventoryVisibleFilterState:
            return InventoryVisibleFilterState(
                search_text="",
                use_filter="",
                category_filters=(),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="",
                stock_filter="",
                conteo_filter="",
                precio_filter=precio_filter,
                precio_text_filter=precio_text_filter,
            )

        def pasa(**kwargs: str) -> bool:
            return inventory_row_matches_visible_filters(
                row, filters=filtros(**kwargs), search_matcher=lambda *_args: True
            )

        self.assertTrue(pasa(precio_text_filter="175"))
        self.assertFalse(pasa(precio_text_filter="250"))
        self.assertTrue(pasa(precio_filter="100_199"))
        self.assertFalse(pasa(precio_filter="200_499"))

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
                "origen_legacy": False,
                "fallback_importacion": False,
                "ultimo_conteo_at": None,
                "stock_minimo": None,
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
                "origen_legacy": True,
                "fallback_importacion": True,
                "ultimo_conteo_at": None,
                "stock_minimo": None,
            },
        ]

        visible_rows = filter_visible_inventory_rows(
            rows,
            filters=InventoryVisibleFilterState(
                search_text="sku-001",
                use_filter="",
                category_filters=(),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="active",
                stock_filter="available",
                conteo_filter="",
                precio_filter="",
                precio_text_filter="",
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
            "origen_legacy": False,
            "fallback_importacion": False,
            "ultimo_conteo_at": None,
            "stock_minimo": None,
            "precio_venta": "150.00",
        }
        search_matcher = Mock(return_value=True)

        matches = inventory_row_matches_visible_filters(
            row,
            filters=InventoryVisibleFilterState(
                search_text="sku",
                use_filter="",
                category_filters=("Calzado",),
                brand_filters=(),
                school_filters=(),
                type_filters=(),
                piece_filters=(),
                size_filters=(),
                color_filters=(),
                status_filter="",
                stock_filter="",
                conteo_filter="",
                precio_filter="",
                precio_text_filter="",
            ),
            search_matcher=search_matcher,
        )

        self.assertFalse(matches)
        search_matcher.assert_not_called()

    def test_inventory_row_matches_visible_filters_can_filter_by_use(self) -> None:
        uniform_row = {
            "categoria_nombre": "Básico",
            "marca_nombre": "Marca Norte",
            "escuela_nombre": "General",
            "tipo_prenda_nombre": "Deportivo",
            "tipo_pieza_nombre": "Pants",
            "talla": "16",
            "color": "Azul",
            "variante_activa": True,
            "stock_actual": 5,
            "origen_legacy": False,
            "fallback_importacion": False,
            "ultimo_conteo_at": None,
            "stock_minimo": None,
            "precio_venta": "150.00",
        }
        regular_row = {
            **uniform_row,
            "categoria_nombre": "Ropa casual",
            "tipo_prenda_nombre": "Casual",
        }

        self.assertTrue(
            inventory_row_matches_visible_filters(
                uniform_row,
                filters=InventoryVisibleFilterState(
                    search_text="",
                    use_filter="school_only",
                    category_filters=(),
                    brand_filters=(),
                    school_filters=(),
                    type_filters=(),
                    piece_filters=(),
                    size_filters=(),
                    color_filters=(),
                    status_filter="",
                    stock_filter="",
                    conteo_filter="",
                    precio_filter="",
                    precio_text_filter="",
                ),
                search_matcher=lambda *_args: True,
            )
        )
        self.assertTrue(
            inventory_row_matches_visible_filters(
                regular_row,
                filters=InventoryVisibleFilterState(
                    search_text="",
                    use_filter="general_only",
                    category_filters=(),
                    brand_filters=(),
                    school_filters=(),
                    type_filters=(),
                    piece_filters=(),
                    size_filters=(),
                    color_filters=(),
                    status_filter="",
                    stock_filter="",
                    conteo_filter="",
                    precio_filter="",
                    precio_text_filter="",
                ),
                search_matcher=lambda *_args: True,
            )
        )
        self.assertFalse(
            inventory_row_matches_visible_filters(
                regular_row,
                filters=InventoryVisibleFilterState(
                    search_text="",
                    use_filter="school_only",
                    category_filters=(),
                    brand_filters=(),
                    school_filters=(),
                    type_filters=(),
                    piece_filters=(),
                    size_filters=(),
                    color_filters=(),
                    status_filter="",
                    stock_filter="",
                    conteo_filter="",
                    precio_filter="",
                    precio_text_filter="",
                ),
                search_matcher=lambda *_args: True,
            )
        )


if __name__ == "__main__":
    unittest.main()
