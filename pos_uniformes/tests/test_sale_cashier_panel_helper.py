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
            selected_client_label="CLI-001 · Maria",
            can_sell=True,
            has_cash_session=True,
            is_processing=False,
        )

        self.assertEqual(panel_view.cashier_view.summary.total_label, "$180.00")
        self.assertIn("datos bancarios", panel_view.payment_tooltip)
        self.assertIn("referencia de transferencia", panel_view.payment_tooltip)
        self.assertTrue(panel_view.remove_enabled)
        self.assertTrue(panel_view.clear_enabled)
        self.assertTrue(panel_view.quick_adjust_enabled)
        self.assertIn("Cliente: CLI-001 · Maria", panel_view.context_label)
        self.assertIn("Pago: Transferencia", panel_view.context_label)
        self.assertEqual(panel_view.status_label, "Lista para cobrar por transferencia.")
        self.assertEqual(panel_view.status_tone, "positive")

    def test_build_sale_cashier_panel_view_without_items_disables_actions(self) -> None:
        panel_view = build_sale_cashier_panel_view(
            sale_cart=[],
            subtotal=Decimal("0.00"),
            applied_discount=Decimal("0.00"),
            rounding_adjustment=Decimal("0.00"),
            collected_total=Decimal("0.00"),
            payment_method="",
            winner_label="Sin descuento",
            selected_client_label="",
            can_sell=True,
            has_cash_session=False,
            is_processing=False,
        )

        self.assertFalse(panel_view.remove_enabled)
        self.assertFalse(panel_view.clear_enabled)
        self.assertFalse(panel_view.quick_adjust_enabled)
        self.assertIn("Mostrador / sin cliente", panel_view.context_label)
        self.assertIn("efectivo", panel_view.payment_tooltip)
        self.assertEqual(panel_view.status_label, "Caja cerrada: abre caja antes de cobrar.")
        self.assertEqual(panel_view.status_tone, "danger")


if __name__ == "__main__":
    unittest.main()
