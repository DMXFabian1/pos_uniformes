from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.layaway_payment_service import (
    build_layaway_payment_input,
    normalize_layaway_payment_method,
    resolve_layaway_payment_state,
)


class LayawayPaymentServiceTests(unittest.TestCase):
    def test_normalize_defaults_to_efectivo_for_unknown_method(self) -> None:
        self.assertEqual(normalize_layaway_payment_method("Tarjeta"), "Efectivo")

    def test_resolve_state_for_cash_disables_field_and_matches_amount(self) -> None:
        state = resolve_layaway_payment_state(payment_method="Efectivo", amount=Decimal("250.00"))

        self.assertEqual(state.cash_amount, Decimal("250.00"))
        self.assertFalse(state.cash_enabled)
        self.assertEqual(state.cash_maximum, Decimal("250.00"))

    def test_resolve_state_for_transfer_zeroes_cash(self) -> None:
        state = resolve_layaway_payment_state(
            payment_method="Transferencia",
            amount=Decimal("180.00"),
            current_cash_amount=Decimal("20.00"),
        )

        self.assertEqual(state.cash_amount, Decimal("0.00"))
        self.assertFalse(state.cash_enabled)

    def test_resolve_state_for_mixed_clamps_cash_to_amount(self) -> None:
        state = resolve_layaway_payment_state(
            payment_method="Mixto",
            amount=Decimal("90.00"),
            current_cash_amount=Decimal("120.00"),
        )

        self.assertEqual(state.cash_amount, Decimal("90.00"))
        self.assertTrue(state.cash_enabled)
        self.assertEqual(state.cash_maximum, Decimal("90.00"))

    def test_build_input_applies_method_rules_and_trims_text(self) -> None:
        payment_input = build_layaway_payment_input(
            amount="150",
            payment_method="Transferencia",
            cash_amount="50",
            reference="  REF-99  ",
            notes="  Pago parcial  ",
        )

        self.assertEqual(payment_input.amount, Decimal("150.00"))
        self.assertEqual(payment_input.payment_method, "Transferencia")
        self.assertEqual(payment_input.cash_amount, Decimal("0.00"))
        self.assertEqual(payment_input.reference, "REF-99")
        self.assertEqual(payment_input.notes, "Pago parcial")


if __name__ == "__main__":
    unittest.main()
