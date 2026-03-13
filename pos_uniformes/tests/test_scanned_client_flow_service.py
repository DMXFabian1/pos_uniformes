from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.scanned_client_flow_service import (
    build_client_already_linked_feedback,
    build_scanned_client_applied_feedback,
    build_client_linked_feedback,
    build_replace_client_confirmation,
    build_scanned_client_kept_feedback,
    decide_scanned_client_action,
)


class ScannedClientFlowServiceTests(unittest.TestCase):
    def test_decision_marks_already_linked_when_same_client(self) -> None:
        decision = decide_scanned_client_action(
            current_client_id=4,
            scanned_client_id=4,
            has_sale_cart=True,
        )
        self.assertEqual(decision.action, "already_linked")

    def test_decision_requires_confirmation_when_cart_exists_and_client_changes(self) -> None:
        decision = decide_scanned_client_action(
            current_client_id=4,
            scanned_client_id=8,
            has_sale_cart=True,
        )
        self.assertEqual(decision.action, "confirm_replace")

    def test_decision_applies_directly_when_no_client_or_empty_cart(self) -> None:
        direct = decide_scanned_client_action(
            current_client_id=None,
            scanned_client_id=8,
            has_sale_cart=False,
        )
        self.assertEqual(direct.action, "apply")
        empty_cart = decide_scanned_client_action(
            current_client_id=4,
            scanned_client_id=8,
            has_sale_cart=False,
        )
        self.assertEqual(empty_cart.action, "apply")

    def test_build_replace_client_confirmation_preserves_warning_text(self) -> None:
        message = build_replace_client_confirmation(
            current_label="Cliente actual",
            scanned_client_code="CLI001",
            scanned_client_name="Maria",
        )
        self.assertIn("Ya hay un cliente enlazado: Cliente actual", message)
        self.assertIn("Se escaneo el QR de CLI001 · Maria.", message)
        self.assertIn("Cambiar el cliente actual puede modificar el descuento aplicado.", message)
        self.assertIn("Deseas reemplazarlo?", message)

    def test_feedback_messages_match_expected_copy(self) -> None:
        self.assertEqual(
            build_client_already_linked_feedback("CLI001"),
            "Cliente CLI001 ya estaba enlazado.",
        )
        self.assertEqual(
            build_scanned_client_kept_feedback(),
            "QR de cliente detectado, pero se conservo el cliente actual.",
        )
        self.assertEqual(
            build_client_linked_feedback(
                client_code="CLI001",
                client_name="Maria",
                discount_label="10%",
            ),
            "Cliente enlazado: CLI001 · Maria. Descuento vigente: 10%.",
        )

    def test_build_scanned_client_applied_feedback_uses_zero_label_when_discount_is_empty(self) -> None:
        feedback = build_scanned_client_applied_feedback(
            client_code="CLI001",
            client_name="Maria",
            discount_percent=Decimal("0.00"),
            format_discount_label=lambda value: f"{value}%",
        )

        self.assertEqual(feedback.tone, "positive")
        self.assertEqual(feedback.auto_clear_ms, 2200)
        self.assertEqual(
            feedback.message,
            "Cliente enlazado: CLI001 · Maria. Descuento vigente: 0%.",
        )
