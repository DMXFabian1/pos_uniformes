from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.inventory_table_row_helper import (
    build_inventory_table_row_view,
    build_inventory_table_row_views,
)


class InventoryTableRowHelperTests(unittest.TestCase):
    def test_build_inventory_table_row_view_for_low_stock_pending_qr(self) -> None:
        view = build_inventory_table_row_view(
            {
                "variante_id": 8,
                "sku": "SKU-008",
                "producto_nombre_base": "Pants Deportivo",
                "talla": "16",
                "color": "Azul Marino",
                "stock_actual": 2,
                "apartado_cantidad": 1,
                "variante_activa": False,
                "qr_exists": False,
            }
        )

        self.assertEqual(view.variant_id, 8)
        self.assertEqual(
            view.values,
            ("SKU-008", "Pants Deportivo", "16", "Azul Marino", "2 Bajo", 1, "INACTIVA", "Pendiente"),
        )
        self.assertEqual(view.stock_tone, "warning")
        self.assertEqual(view.committed_tone, "warning")
        self.assertEqual(view.status_tone, "muted")
        self.assertEqual(view.qr_tone, "warning")

    def test_build_inventory_table_row_views_for_multiple_rows(self) -> None:
        views = build_inventory_table_row_views(
            [
                {
                    "variante_id": 1,
                    "sku": "SKU-001",
                    "producto_nombre_base": "Camisa Oficial",
                    "talla": "12",
                    "color": "Blanco",
                    "stock_actual": 0,
                    "apartado_cantidad": 0,
                    "variante_activa": True,
                    "qr_exists": True,
                },
                {
                    "variante_id": 2,
                    "sku": "SKU-002",
                    "producto_nombre_base": "Pants Deportivo",
                    "talla": "14",
                    "color": "Azul",
                    "stock_actual": 6,
                    "apartado_cantidad": 0,
                    "variante_activa": True,
                    "qr_exists": False,
                },
            ]
        )

        self.assertEqual(len(views), 2)
        self.assertEqual(views[0].values[4], "0 Agotado")
        self.assertEqual(views[0].stock_tone, "danger")
        self.assertEqual(views[1].values[4], "6 OK")
        self.assertEqual(views[1].stock_tone, "positive")


if __name__ == "__main__":
    unittest.main()
