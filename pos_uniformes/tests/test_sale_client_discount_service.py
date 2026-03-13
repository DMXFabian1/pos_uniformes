from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_client_discount_service import resolve_sale_client_discount
from pos_uniformes.services.sale_discount_service import normalize_discount_value


class SaleClientDiscountServiceTests(unittest.TestCase):
    def test_prefers_client_specific_discount_when_present(self) -> None:
        result = resolve_sale_client_discount(
            preferred_discount=Decimal("12.50"),
            loyalty_discount=Decimal("10.00"),
            normalize_discount_value=normalize_discount_value,
        )

        self.assertEqual(result, Decimal("12.50"))

    def test_falls_back_to_loyalty_discount_when_preferred_is_zero(self) -> None:
        result = resolve_sale_client_discount(
            preferred_discount=Decimal("0.00"),
            loyalty_discount=Decimal("10.00"),
            normalize_discount_value=normalize_discount_value,
        )

        self.assertEqual(result, Decimal("10.00"))

    def test_normalizes_invalid_values_to_zero(self) -> None:
        result = resolve_sale_client_discount(
            preferred_discount="",
            loyalty_discount="abc",
            normalize_discount_value=normalize_discount_value,
        )

        self.assertEqual(result, Decimal("0.00"))
