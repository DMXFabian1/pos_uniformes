from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_cart_table_service import build_sale_cart_table_view


class SaleCartTableServiceTests(unittest.TestCase):
    def test_builds_empty_view_for_empty_cart(self) -> None:
        view = build_sale_cart_table_view([])

        self.assertEqual(view.rows, ())
        self.assertEqual(view.total_items, 0)

    def test_builds_table_rows_and_counts_total_items(self) -> None:
        view = build_sale_cart_table_view(
            [
                {
                    "sku": "SKU-001",
                    "producto_nombre": "Playera",
                    "cantidad": 2,
                    "precio_unitario": Decimal("199.00"),
                },
                {
                    "sku": "SKU-002",
                    "producto_nombre": "Pantalon",
                    "cantidad": 1,
                    "precio_unitario": Decimal("350.00"),
                },
            ]
        )

        self.assertEqual(view.total_items, 3)
        self.assertEqual(len(view.rows), 2)
        self.assertEqual(
            view.rows[0].values,
            ("SKU-001", "Playera", 2, Decimal("199.00"), Decimal("398.00")),
        )
        self.assertEqual(
            view.rows[1].values,
            ("SKU-002", "Pantalon", 1, Decimal("350.00"), Decimal("350.00")),
        )


if __name__ == "__main__":
    unittest.main()
