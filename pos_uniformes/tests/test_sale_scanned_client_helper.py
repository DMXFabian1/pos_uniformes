from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.sale_scanned_client_helper import build_sale_scanned_client_ui_state


class SaleScannedClientHelperTests(unittest.TestCase):
    def test_returns_immediate_feedback_when_client_is_already_linked(self) -> None:
        state = build_sale_scanned_client_ui_state(
            current_client_id=4,
            current_client_label="CLI004 · Maria",
            scanned_client_id=4,
            scanned_client_code="CLI004",
            scanned_client_name="Maria",
            has_sale_cart=True,
            discount_percent=Decimal("10.00"),
            format_discount_label=lambda value: f"{value}%",
        )

        self.assertEqual(state.action, "already_linked")
        self.assertEqual(state.immediate_feedback.message, "Cliente CLI004 ya estaba enlazado.")
        self.assertEqual(state.immediate_feedback.tone, "neutral")
        self.assertEqual(state.immediate_feedback.auto_clear_ms, 1700)

    def test_returns_confirmation_and_rejected_feedback_when_cart_exists(self) -> None:
        state = build_sale_scanned_client_ui_state(
            current_client_id=4,
            current_client_label="CLI004 · Maria",
            scanned_client_id=8,
            scanned_client_code="CLI008",
            scanned_client_name="Luisa",
            has_sale_cart=True,
            discount_percent=Decimal("0.00"),
            format_discount_label=lambda value: f"{value}%",
        )

        self.assertEqual(state.action, "confirm_replace")
        self.assertIn("Ya hay un cliente enlazado: CLI004 · Maria", state.confirmation_message)
        self.assertIn("Se escaneo el QR de CLI008 · Luisa.", state.confirmation_message)
        self.assertEqual(
            state.rejected_feedback.message,
            "QR de cliente detectado, pero se conservo el cliente actual.",
        )
        self.assertEqual(state.rejected_feedback.tone, "warning")
        self.assertEqual(state.applied_feedback.message, "Cliente enlazado: CLI008 · Luisa. Descuento vigente: 0%.")

    def test_returns_apply_feedback_when_client_can_be_applied_directly(self) -> None:
        state = build_sale_scanned_client_ui_state(
            current_client_id=None,
            current_client_label="Mostrador",
            scanned_client_id=8,
            scanned_client_code="CLI008",
            scanned_client_name="Luisa",
            has_sale_cart=False,
            discount_percent=Decimal("15.00"),
            format_discount_label=lambda value: f"{value}%",
        )

        self.assertEqual(state.action, "apply")
        self.assertEqual(state.confirmation_message, "")
        self.assertIsNone(state.immediate_feedback)
        self.assertIsNone(state.rejected_feedback)
        self.assertEqual(state.applied_feedback.tone, "positive")
        self.assertEqual(
            state.applied_feedback.message,
            "Cliente enlazado: CLI008 · Luisa. Descuento vigente: 15.00%.",
        )


if __name__ == "__main__":
    unittest.main()
