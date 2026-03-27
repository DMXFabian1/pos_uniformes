from __future__ import annotations

import unittest

from pos_uniformes.services.inventory_count_service import InventoryCountRow
from pos_uniformes.ui.helpers.inventory_count_view_helper import build_inventory_count_batch_view


class InventoryCountViewHelperTests(unittest.TestCase):
    def test_build_inventory_count_batch_view_empty(self) -> None:
        view = build_inventory_count_batch_view([])

        self.assertEqual(view.rows, ())
        self.assertEqual(view.summary_label, "Lote vacio.")

    def test_build_inventory_count_batch_view_with_rows(self) -> None:
        view = build_inventory_count_batch_view(
            [
                InventoryCountRow(
                    variante_id=1,
                    sku="SKU000001",
                    producto_nombre="Bata",
                    stock_sistema=2,
                    stock_contado=4,
                    delta=2,
                ),
                InventoryCountRow(
                    variante_id=2,
                    sku="SKU000002",
                    producto_nombre="Playera",
                    stock_sistema=5,
                    stock_contado=3,
                    delta=-2,
                ),
            ]
        )

        self.assertEqual(len(view.rows), 2)
        self.assertEqual(
            view.rows[0].values,
            ("SKU000001", "Bata", 2, 4, "+2"),
        )
        self.assertEqual(view.summary_label, "Filas con diferencia: 2 | Suben: 1 | Bajan: 1")
        self.assertEqual(view.confirmation_lines[0], "Filas capturadas: 2")


if __name__ == "__main__":
    unittest.main()
