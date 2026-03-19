from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.sale_post_action_feedback_helper import (
    build_sale_cancel_post_action_view,
    build_sale_checkout_post_action_view,
)


class SalePostActionFeedbackHelperTests(unittest.TestCase):
    def test_build_sale_checkout_post_action_view_includes_feedback_and_notice(self) -> None:
        view = build_sale_checkout_post_action_view(
            folio="VTA-001",
            total=Decimal("169.00"),
            payment_method="Efectivo",
            loyalty_transition_notice="Cliente sube a nivel Plata.",
        )

        self.assertEqual(
            view.feedback_message,
            "Venta VTA-001 registrada. Total cobrado: 169.00 via Efectivo.",
        )
        self.assertEqual(view.feedback_tone, "positive")
        self.assertEqual(view.feedback_auto_clear_ms, 2200)
        self.assertTrue(view.refresh_all)
        self.assertTrue(view.clear_sale_cart)
        self.assertTrue(view.reset_sale_form)
        self.assertTrue(view.focus_sale_input)
        self.assertTrue(view.play_feedback_sound)
        self.assertEqual(view.notice_title, "Nivel actualizado para siguiente compra")
        self.assertEqual(view.notice_message, "Cliente sube a nivel Plata.")

    def test_build_sale_checkout_post_action_view_omits_empty_notice(self) -> None:
        view = build_sale_checkout_post_action_view(
            folio="VTA-002",
            total=Decimal("250.00"),
            payment_method="Transferencia",
            loyalty_transition_notice="   ",
        )

        self.assertIsNone(view.notice_title)
        self.assertIsNone(view.notice_message)

    def test_build_sale_cancel_post_action_view_uses_warning_feedback(self) -> None:
        view = build_sale_cancel_post_action_view()

        self.assertEqual(view.feedback_message, "Venta cancelada correctamente.")
        self.assertEqual(view.feedback_tone, "warning")
        self.assertEqual(view.feedback_auto_clear_ms, 1800)
        self.assertTrue(view.refresh_all)
        self.assertFalse(view.clear_sale_cart)
        self.assertFalse(view.reset_sale_form)
        self.assertFalse(view.focus_sale_input)
        self.assertFalse(view.play_feedback_sound)


if __name__ == "__main__":
    unittest.main()
