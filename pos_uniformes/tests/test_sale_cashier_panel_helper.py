from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.sale_cashier_panel_helper import build_sale_cashier_panel_view


class SaleCashierPanelHelperTests(unittest.TestCase):
    def test_build_sale_cashier_panel_view(self) -> None:
        panel_view = build_sale_cashier_panel_view(
            sale_cart=[
                {
                    "sku": "SKU-1",
                    "producto_nombre": "Pants",
                    "cantidad": 2,
                    "precio_unitario": Decimal("100.00"),
                }
            ],
            subtotal=Decimal("200.00"),
            applied_discount=Decimal("20.00"),
            rounding_adjustment=Decimal("0.00"),
            collected_total=Decimal("180.00"),
            payment_method="Transferencia",
            winner_label="Promocion manual 10%",
            can_sell=True,
        )

        self.assertEqual(panel_view.cashier_view.summary.total_label, "$180.00")
        self.assertEqual(
            panel_view.payment_tooltip,
            "El cobro se completara en una ventana aparte para transferencia.",
        )
        self.assertTrue(panel_view.remove_enabled)
        self.assertTrue(panel_view.clear_enabled)

    def test_build_sale_cashier_panel_view_without_items_disables_actions(self) -> None:
        panel_view = build_sale_cashier_panel_view(
            sale_cart=[],
            subtotal=Decimal("0.00"),
            applied_discount=Decimal("0.00"),
            rounding_adjustment=Decimal("0.00"),
            collected_total=Decimal("0.00"),
            payment_method="",
            winner_label="Sin descuento",
            can_sell=True,
        )

        self.assertFalse(panel_view.remove_enabled)
        self.assertFalse(panel_view.clear_enabled)
        self.assertIn("efectivo", panel_view.payment_tooltip)


if __name__ == "__main__":
    unittest.main()
