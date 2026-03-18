from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.sale_cashier_view_helper import build_sale_cashier_view


class SaleCashierViewHelperTests(unittest.TestCase):
    def test_builds_empty_cashier_view(self) -> None:
        view = build_sale_cashier_view(
            sale_cart=[],
            subtotal=Decimal("0.00"),
            applied_discount=Decimal("0.00"),
            rounding_adjustment=Decimal("0.00"),
            collected_total=Decimal("0.00"),
            payment_method="Efectivo",
            winner_label="Sin descuento",
        )

        self.assertEqual(view.table_view.rows, ())
        self.assertEqual(view.table_view.total_items, 0)
        self.assertEqual(view.summary.total_label, "$0.00")
        self.assertEqual(view.summary.meta_label, "Total a cobrar")
        self.assertEqual(view.summary.summary_label, "Carrito vacio.")

    def test_builds_table_and_summary_in_one_view(self) -> None:
        view = build_sale_cashier_view(
            sale_cart=[
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
            ],
            subtotal=Decimal("748.00"),
            applied_discount=Decimal("74.80"),
            rounding_adjustment=Decimal("0.00"),
            collected_total=Decimal("673.20"),
            payment_method="Transferencia",
            winner_label="Lealtad Profesor 10%",
        )

        self.assertEqual(len(view.table_view.rows), 2)
        self.assertEqual(view.table_view.total_items, 3)
        self.assertEqual(view.summary.total_label, "$673.20")
        self.assertEqual(view.summary.meta_label, "Transferencia | Lealtad Profesor 10%")
        self.assertEqual(
            view.summary.summary_label,
            "Lineas: 2 | Piezas: 3 | Subtotal: $748.00 | Descuento: $74.80",
        )


if __name__ == "__main__":
    unittest.main()
