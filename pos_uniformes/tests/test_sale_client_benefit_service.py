from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.database.models import NivelLealtad
from pos_uniformes.services.sale_client_benefit_service import resolve_sale_client_benefit
from pos_uniformes.services.sale_discount_service import normalize_discount_value


class SaleClientBenefitServiceTests(unittest.TestCase):
    def test_prefers_client_specific_discount_and_uses_loyalty_label(self) -> None:
        result = resolve_sale_client_benefit(
            preferred_discount=Decimal("12.50"),
            loyalty_level=NivelLealtad.PROFESOR,
            loyalty_discount_resolver=lambda _level: Decimal("15.00"),
            normalize_discount_value=normalize_discount_value,
        )

        self.assertEqual(result.discount_percent, Decimal("12.50"))
        self.assertEqual(result.source_label, "Profesor")

    def test_falls_back_to_loyalty_discount_when_client_has_no_preferred_discount(self) -> None:
        result = resolve_sale_client_benefit(
            preferred_discount=Decimal("0.00"),
            loyalty_level=NivelLealtad.LEAL,
            loyalty_discount_resolver=lambda _level: Decimal("10.00"),
            normalize_discount_value=normalize_discount_value,
        )

        self.assertEqual(result.discount_percent, Decimal("10.00"))
        self.assertEqual(result.source_label, "Leal")

    def test_normalizes_invalid_values_to_zero_but_preserves_basic_label(self) -> None:
        result = resolve_sale_client_benefit(
            preferred_discount="",
            loyalty_level=None,
            loyalty_discount_resolver=lambda _level: Decimal("0.00"),
            normalize_discount_value=normalize_discount_value,
        )

        self.assertEqual(result.discount_percent, Decimal("0.00"))
        self.assertEqual(result.source_label, "Basico")


if __name__ == "__main__":
    unittest.main()
