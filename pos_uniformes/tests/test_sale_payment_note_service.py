from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_payment_note_service import (
    build_cash_payment_details,
    build_mixed_payment_details,
    build_transfer_payment_details,
    empty_sale_payment_details,
)


class SalePaymentNoteServiceTests(unittest.TestCase):
    def test_build_cash_payment_details_keeps_expected_notes(self) -> None:
        details = build_cash_payment_details(
            received=Decimal("200.00"),
            change=Decimal("30.85"),
            reference="Caja 1",
        )

        self.assertEqual(
            details.note_lines,
            (
                "Recibido: 200.00",
                "Cambio: 30.85",
                "Referencia: Caja 1",
            ),
        )

    def test_build_transfer_payment_details_defaults_reference(self) -> None:
        details = build_transfer_payment_details()

        self.assertEqual(
            details.note_lines,
            ("Referencia transferencia: Sin referencia",),
        )

    def test_build_mixed_payment_details_normalizes_amounts(self) -> None:
        details = build_mixed_payment_details(
            transfer_amount="150",
            cash_received="80",
            change="9.5",
            reference="TRX-123",
        )

        self.assertEqual(
            details.note_lines,
            (
                "Transferencia: 150.00",
                "Efectivo recibido: 80.00",
                "Cambio: 9.50",
                "Referencia transferencia: TRX-123",
            ),
        )

    def test_empty_payment_details_has_no_notes(self) -> None:
        self.assertEqual(empty_sale_payment_details().note_lines, ())


if __name__ == "__main__":
    unittest.main()
