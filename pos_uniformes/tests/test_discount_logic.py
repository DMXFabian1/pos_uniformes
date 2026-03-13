from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_discount_service import (
    build_sale_discount_breakdown,
    calculate_sale_pricing,
    calculate_sale_totals,
    effective_sale_discount_percent,
    format_discount_label,
    normalize_discount_value,
)


class DiscountLogicTests(unittest.TestCase):
    def test_normalize_discount_value_rejects_invalid_input(self) -> None:
        self.assertEqual(normalize_discount_value(None), Decimal("0.00"))
        self.assertEqual(normalize_discount_value("abc"), Decimal("0.00"))
        self.assertEqual(normalize_discount_value("12.5"), Decimal("12.50"))

    def test_format_discount_label_trims_trailing_zeroes(self) -> None:
        self.assertEqual(format_discount_label(Decimal("10.00")), "10%")
        self.assertEqual(format_discount_label(Decimal("12.50")), "12.5%")

    def test_effective_discount_uses_the_greater_benefit(self) -> None:
        result = effective_sale_discount_percent(
            loyalty_discount=Decimal("10.00"),
            promo_discount=Decimal("15.00"),
        )

        self.assertEqual(result, Decimal("15.00"))

    def test_breakdown_prioritizes_manual_promo_when_higher(self) -> None:
        breakdown = build_sale_discount_breakdown(
            loyalty_discount=Decimal("10.00"),
            promo_discount=Decimal("15.00"),
            loyalty_source="LEAL",
        )

        self.assertEqual(breakdown["winner_source"], "PROMOCION_MANUAL")
        self.assertEqual(breakdown["effective_discount"], Decimal("15.00"))
        self.assertEqual(breakdown["winner_label"], "Promocion manual 15%")

    def test_breakdown_prioritizes_loyalty_when_equal_or_higher(self) -> None:
        breakdown = build_sale_discount_breakdown(
            loyalty_discount=Decimal("15.00"),
            promo_discount=Decimal("10.00"),
            loyalty_source="Profesor",
        )

        self.assertEqual(breakdown["winner_source"], "LEALTAD")
        self.assertEqual(breakdown["effective_discount"], Decimal("15.00"))
        self.assertEqual(breakdown["winner_label"], "Lealtad Profesor 15%")

    def test_calculate_sale_totals_caps_discount_to_subtotal(self) -> None:
        subtotal, discount_percent, applied_discount, total = calculate_sale_totals(
            [
                {"precio_unitario": "50.00", "cantidad": 2},
            ],
            loyalty_discount=Decimal("110.00"),
            promo_discount=Decimal("0.00"),
        )

        self.assertEqual(subtotal, Decimal("100.00"))
        self.assertEqual(discount_percent, Decimal("110.00"))
        self.assertEqual(applied_discount, Decimal("100.00"))
        self.assertEqual(total, Decimal("0.00"))

    def test_calculate_sale_pricing_keeps_discount_and_rounding_separate(self) -> None:
        pricing = calculate_sale_pricing(
            [
                {"precio_unitario": "199.00", "cantidad": 1},
            ],
            loyalty_discount=Decimal("15.00"),
            promo_discount=Decimal("0.00"),
        )

        self.assertEqual(pricing.subtotal, Decimal("199.00"))
        self.assertEqual(pricing.applied_discount, Decimal("29.85"))
        self.assertEqual(pricing.total_after_discount, Decimal("169.15"))
        self.assertEqual(pricing.rounding_adjustment, Decimal("-0.15"))
        self.assertEqual(pricing.collected_total, Decimal("169.00"))
