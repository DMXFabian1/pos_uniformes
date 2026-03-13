from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.sale_cashier_summary_helper import build_sale_cashier_summary


class SaleCashierSummaryServiceTests(unittest.TestCase):
    def test_returns_empty_state_when_cart_has_no_items(self) -> None:
        summary = build_sale_cashier_summary(
            has_items=False,
            lines_count=0,
            total_items=0,
            subtotal=Decimal("0.00"),
            applied_discount=Decimal("0.00"),
            rounding_adjustment=Decimal("0.00"),
            collected_total=Decimal("0.00"),
            payment_method="Efectivo",
            winner_label="Sin descuento",
        )

        self.assertEqual(summary.total_label, "$0.00")
        self.assertEqual(summary.meta_label, "Total a cobrar")
        self.assertEqual(summary.summary_label, "Carrito vacio.")

    def test_builds_compact_total_block_without_customer_reference(self) -> None:
        summary = build_sale_cashier_summary(
            has_items=True,
            lines_count=2,
            total_items=5,
            subtotal=Decimal("450.00"),
            applied_discount=Decimal("45.00"),
            rounding_adjustment=Decimal("0.00"),
            collected_total=Decimal("405.00"),
            payment_method="Transferencia",
            winner_label="Lealtad Profesor 10%",
        )

        self.assertEqual(summary.total_label, "$405.00")
        self.assertEqual(summary.meta_label, "Transferencia | Lealtad Profesor 10%")
        self.assertEqual(
            summary.summary_label,
            "Lineas: 2 | Piezas: 5 | Subtotal: $450.00 | Descuento: $45.00",
        )
        self.assertNotIn("Cliente", summary.meta_label)
        self.assertNotIn("Maria Fernanda", summary.meta_label)
        self.assertNotIn("Cliente", summary.summary_label)
        self.assertNotIn("Maria Fernanda", summary.summary_label)

    def test_includes_rounding_adjustment_when_present(self) -> None:
        summary = build_sale_cashier_summary(
            has_items=True,
            lines_count=1,
            total_items=1,
            subtotal=Decimal("199.00"),
            applied_discount=Decimal("29.85"),
            rounding_adjustment=Decimal("-0.15"),
            collected_total=Decimal("169.00"),
            payment_method="Efectivo",
            winner_label="Promocion manual 15%",
        )

        self.assertEqual(summary.total_label, "$169.00")
        self.assertEqual(summary.meta_label, "Efectivo | Promocion manual 15%")
        self.assertEqual(
            summary.summary_label,
            "Lineas: 1 | Piezas: 1 | Subtotal: $199.00 | Descuento: $29.85 | Ajuste: $-0.15",
        )


if __name__ == "__main__":
    unittest.main()
