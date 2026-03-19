from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.sale_payment_validation_service import (
    validate_cash_payment,
    validate_mixed_payment,
    validate_transfer_payment_availability,
)


class SalePaymentValidationServiceTests(unittest.TestCase):
    def test_validate_cash_payment_reports_shortfall(self) -> None:
        validation = validate_cash_payment(total=Decimal("150.00"), received=Decimal("100.00"))

        self.assertFalse(validation.is_sufficient)
        self.assertEqual(validation.change, Decimal("0.00"))
        self.assertEqual(validation.status_tone, "warning")

    def test_validate_cash_payment_reports_change(self) -> None:
        validation = validate_cash_payment(total=Decimal("150.00"), received=Decimal("200.00"))

        self.assertTrue(validation.is_sufficient)
        self.assertEqual(validation.change, Decimal("50.00"))
        self.assertEqual(validation.status_tone, "positive")

    def test_validate_transfer_payment_availability_requires_configuration(self) -> None:
        error_message = validate_transfer_payment_availability(
            SimpleNamespace(transfer_clabe="", transfer_instructions="")
        )
        self.assertIn("Configura CLABE", str(error_message))

    def test_validate_mixed_payment_calculates_cash_due_and_change(self) -> None:
        validation = validate_mixed_payment(
            total=Decimal("300.00"),
            transfer_amount=Decimal("200.00"),
            cash_received=Decimal("150.00"),
        )

        self.assertTrue(validation.is_sufficient)
        self.assertEqual(validation.cash_due, Decimal("100.00"))
        self.assertEqual(validation.change, Decimal("50.00"))

    def test_validate_mixed_payment_rejects_insufficient_sum(self) -> None:
        validation = validate_mixed_payment(
            total=Decimal("300.00"),
            transfer_amount=Decimal("100.00"),
            cash_received=Decimal("150.00"),
        )

        self.assertFalse(validation.is_sufficient)
        self.assertEqual(validation.cash_due, Decimal("200.00"))
        self.assertIn("debe cubrir el total", str(validation.error_message))


if __name__ == "__main__":
    unittest.main()
