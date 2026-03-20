from __future__ import annotations

from decimal import Decimal
import unittest
from unittest.mock import patch

from pos_uniformes.services.layaway_pricing_service import (
    build_layaway_pricing,
    resolve_layaway_client_discount_percent,
    resolve_layaway_min_deposit,
    resolve_layaway_unit_price,
)


class LayawayPricingServiceTests(unittest.TestCase):
    def test_resolve_layaway_client_discount_percent_returns_zero_without_client(self) -> None:
        session = object()

        result = resolve_layaway_client_discount_percent(session, selected_client_id=None)

        self.assertEqual(result, Decimal("0.00"))

    def test_resolve_layaway_client_discount_percent_uses_selected_client_benefit(self) -> None:
        session = object()

        with patch(
            "pos_uniformes.services.layaway_pricing_service.load_sale_selected_client_discount_percent",
            return_value=Decimal("12.50"),
        ):
            result = resolve_layaway_client_discount_percent(session, selected_client_id=7)

        self.assertEqual(result, Decimal("12.50"))

    def test_resolve_layaway_unit_price_preserves_base_price_without_discount(self) -> None:
        self.assertEqual(
            resolve_layaway_unit_price(Decimal("200.00"), discount_percent=Decimal("0.00")),
            Decimal("200.00"),
        )

    def test_resolve_layaway_unit_price_applies_discount_percent(self) -> None:
        self.assertEqual(
            resolve_layaway_unit_price(Decimal("200.00"), discount_percent=Decimal("10.00")),
            Decimal("180.00"),
        )

    def test_build_layaway_pricing_uses_sale_rounding_rule(self) -> None:
        pricing = build_layaway_pricing(Decimal("439.24"))

        self.assertEqual(pricing.subtotal, Decimal("439.24"))
        self.assertEqual(pricing.rounding_adjustment, Decimal("0.26"))
        self.assertEqual(pricing.total, Decimal("439.50"))

    def test_resolve_layaway_min_deposit_uses_20_percent_of_total(self) -> None:
        self.assertEqual(resolve_layaway_min_deposit(Decimal("439.00")), Decimal("87.80"))


if __name__ == "__main__":
    unittest.main()
