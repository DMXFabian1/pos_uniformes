from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.catalog_refresh_helper import (
    build_catalog_snapshot_rows,
    build_catalog_table_values,
)


class CatalogRefreshHelperTests(unittest.TestCase):
    def test_build_catalog_snapshot_rows_maps_query_result_tuple(self) -> None:
        snapshot_rows = build_catalog_snapshot_rows(
            [
                (
                    8,
                    2,
                    3,
                    4,
                    None,
                    "SKU-008",
                    "Uniforme",
                    "Marca Norte",
                    None,
                    "Deportivo",
                    None,
                    "Pants Deportivo | Morelos | Pants #4",
                    "Pants Deportivo",
                    "Descripcion",
                    "Pants legacy",
                    True,
                    "16",
                    "Azul Marino",
                    Decimal("219.00"),
                    Decimal("140.00"),
                    6,
                    2,
                    True,
                    False,
                    True,
                )
            ]
        )

        self.assertEqual(len(snapshot_rows), 1)
        row = snapshot_rows[0]
        self.assertEqual(row["escuela_nombre"], "General")
        self.assertEqual(row["tipo_pieza_nombre"], "-")
        self.assertEqual(row["producto_nombre"], "Pants Deportivo | Morelos | Pants")
        self.assertEqual(row["producto_estado"], "ACTIVO")
        self.assertEqual(row["variante_estado"], "INACTIVA")
        self.assertEqual(row["origen_etiqueta"], "LEGACY")
        self.assertTrue(row["fallback_importacion"])
        self.assertEqual(row["fallback_text"], "fallback")

    def test_build_catalog_table_values_returns_visible_columns_in_order(self) -> None:
        table_values = build_catalog_table_values(
            [
                {
                    "sku": "SKU-001",
                    "escuela_nombre": "General",
                    "tipo_prenda_nombre": "Oficial",
                    "tipo_pieza_nombre": "Camisa",
                    "marca_nombre": "Marca Sur",
                    "producto_nombre_base": "Camisa Oficial",
                    "talla": "12",
                    "color": "Blanco",
                    "precio_venta": Decimal("199.00"),
                    "stock_actual": 3,
                    "apartado_cantidad": 1,
                    "variante_estado": "ACTIVA",
                }
            ]
        )

        self.assertEqual(
            table_values,
            (
                (
                    "SKU-001",
                    "General",
                    "Oficial",
                    "Camisa",
                    "Marca Sur",
                    "Camisa Oficial",
                    "12",
                    "Blanco",
                    Decimal("199.00"),
                    3,
                    1,
                    "ACTIVA",
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
