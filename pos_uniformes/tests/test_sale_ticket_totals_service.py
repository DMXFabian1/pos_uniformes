from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_ticket_totals_service import resolve_sale_ticket_totals


class SaleTicketTotalsServiceTests(unittest.TestCase):
    def test_uses_stored_discount_fields_when_present(self) -> None:
        totals = resolve_sale_ticket_totals(
            subtotal=Decimal("199.00"),
            stored_discount_percent=Decimal("10.00"),
            stored_discount_amount=Decimal("19.90"),
            total=Decimal("179.10"),
        )

        self.assertEqual(totals.subtotal, Decimal("199.00"))
        self.assertEqual(totals.discount_percent, Decimal("10.00"))
        self.assertEqual(totals.discount_amount, Decimal("19.90"))
        self.assertEqual(totals.total, Decimal("179.10"))

    def test_infers_discount_from_subtotal_and_total_when_stored_discount_is_zero(self) -> None:
        totals = resolve_sale_ticket_totals(
            subtotal=Decimal("199.00"),
            stored_discount_percent=Decimal("0.00"),
            stored_discount_amount=Decimal("0.00"),
            total=Decimal("169.15"),
        )

        self.assertEqual(totals.discount_amount, Decimal("29.85"))
        self.assertEqual(totals.discount_percent, Decimal("15.00"))

    def test_preserves_total_while_reconstructing_missing_discount_fields(self) -> None:
        totals = resolve_sale_ticket_totals(
            subtotal=Decimal("199.00"),
            stored_discount_percent=Decimal("0.00"),
            stored_discount_amount=Decimal("0.00"),
            total=Decimal("169.15"),
        )

        self.assertEqual(totals.subtotal, Decimal("199.00"))
        self.assertEqual(totals.discount_percent, Decimal("15.00"))
        self.assertEqual(totals.discount_amount, Decimal("29.85"))
        self.assertEqual(totals.total, Decimal("169.15"))

    def test_never_returns_negative_inferred_discount(self) -> None:
        totals = resolve_sale_ticket_totals(
            subtotal=Decimal("100.00"),
            stored_discount_percent=Decimal("0.00"),
            stored_discount_amount=Decimal("0.00"),
            total=Decimal("120.00"),
        )

        self.assertEqual(totals.discount_amount, Decimal("0.00"))
        self.assertEqual(totals.discount_percent, Decimal("0.00"))
