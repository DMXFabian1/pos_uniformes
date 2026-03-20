from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_table_row_helper import (
    build_catalog_table_row_view,
    build_catalog_table_row_views,
)


class CatalogTableRowHelperTests(unittest.TestCase):
    def test_build_catalog_table_row_view_marks_inactive_low_stock_variant(self) -> None:
        view = build_catalog_table_row_view(
            {
                "variante_id": 8,
                "sku": "SKU-008",
                "escuela_nombre": "General",
                "tipo_prenda_nombre": "Accesorio",
                "tipo_pieza_nombre": "Bata",
                "marca_nombre": "Sin marca",
                "producto_nombre_base": "Bata infantil",
                "talla": "12",
                "color": "Azul",
                "precio_venta": 65,
                "stock_actual": 2,
                "apartado_cantidad": 1,
                "variante_activo": False,
                "variante_estado": "INACTIVA",
            }
        )

        self.assertEqual(view.variant_id, 8)
        self.assertEqual(view.row_tone, "muted")
        self.assertEqual(view.stock_tone, "warning")
        self.assertEqual(view.layaway_tone, "warning")
        self.assertEqual(view.status_tone, "muted")

    def test_build_catalog_table_row_views_for_multiple_rows(self) -> None:
        views = build_catalog_table_row_views(
            [
                {
                    "variante_id": 1,
                    "sku": "SKU-001",
                    "escuela_nombre": "General",
                    "tipo_prenda_nombre": "Accesorio",
                    "tipo_pieza_nombre": "Bata",
                    "marca_nombre": "Sin marca",
                    "producto_nombre_base": "Bata 1",
                    "talla": "10",
                    "color": "Blanco",
                    "precio_venta": 65,
                    "stock_actual": 0,
                    "apartado_cantidad": 0,
                    "variante_activo": True,
                    "variante_estado": "ACTIVA",
                },
                {
                    "variante_id": 2,
                    "sku": "SKU-002",
                    "escuela_nombre": "General",
                    "tipo_prenda_nombre": "Accesorio",
                    "tipo_pieza_nombre": "Bata",
                    "marca_nombre": "Sin marca",
                    "producto_nombre_base": "Bata 2",
                    "talla": "12",
                    "color": "Rojo",
                    "precio_venta": 65,
                    "stock_actual": 8,
                    "apartado_cantidad": 1,
                    "variante_activo": True,
                    "variante_estado": "ACTIVA",
                },
            ]
        )

        self.assertEqual(len(views), 2)
        self.assertEqual(views[0].row_tone, "danger")
        self.assertEqual(views[0].stock_tone, "danger")
        self.assertEqual(views[1].row_tone, "reserved")
        self.assertEqual(views[1].layaway_tone, "warning")


if __name__ == "__main__":
    unittest.main()
