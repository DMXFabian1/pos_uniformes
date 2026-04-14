"""Tests para sale_discount_service — funciones puras de descuento."""

from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_discount_service import (
    SalePricing,
    build_sale_discount_breakdown,
    calculate_sale_pricing,
    calculate_sale_totals,
    effective_sale_discount_percent,
    format_discount_label,
    normalize_discount_value,
)


# ---------------------------------------------------------------------------
# normalize_discount_value
# ---------------------------------------------------------------------------

class NormalizeDiscountValueTests(unittest.TestCase):

    def test_none_returns_zero(self) -> None:
        self.assertEqual(normalize_discount_value(None), Decimal("0.00"))

    def test_zero_returns_zero(self) -> None:
        self.assertEqual(normalize_discount_value(0), Decimal("0.00"))

    def test_integer_converted(self) -> None:
        self.assertEqual(normalize_discount_value(10), Decimal("10.00"))

    def test_string_decimal_converted(self) -> None:
        self.assertEqual(normalize_discount_value("12.50"), Decimal("12.50"))

    def test_invalid_string_returns_zero(self) -> None:
        self.assertEqual(normalize_discount_value("no_es_numero"), Decimal("0.00"))

    def test_result_has_two_decimal_places(self) -> None:
        result = normalize_discount_value("5.5")
        self.assertEqual(str(result), "5.50")


# ---------------------------------------------------------------------------
# format_discount_label
# ---------------------------------------------------------------------------

class FormatDiscountLabelTests(unittest.TestCase):

    def test_integer_value_shows_no_decimals(self) -> None:
        self.assertEqual(format_discount_label(Decimal("10.00")), "10%")

    def test_half_value_shows_one_decimal(self) -> None:
        self.assertEqual(format_discount_label(Decimal("12.50")), "12.5%")

    def test_zero_shows_zero_percent(self) -> None:
        self.assertEqual(format_discount_label(Decimal("0.00")), "0%")

    def test_float_input(self) -> None:
        result = format_discount_label(15.0)
        self.assertEqual(result, "15%")


# ---------------------------------------------------------------------------
# effective_sale_discount_percent
# ---------------------------------------------------------------------------

class EffectiveSaleDiscountPercentTests(unittest.TestCase):

    def test_returns_higher_of_loyalty_and_promo(self) -> None:
        result = effective_sale_discount_percent(
            loyalty_discount=Decimal("10.00"),
            promo_discount=Decimal("15.00"),
        )
        self.assertEqual(result, Decimal("15.00"))

    def test_returns_loyalty_when_promo_is_zero(self) -> None:
        result = effective_sale_discount_percent(
            loyalty_discount=Decimal("10.00"),
            promo_discount=Decimal("0.00"),
        )
        self.assertEqual(result, Decimal("10.00"))

    def test_returns_zero_when_both_zero(self) -> None:
        result = effective_sale_discount_percent(
            loyalty_discount=Decimal("0.00"),
            promo_discount=Decimal("0.00"),
        )
        self.assertEqual(result, Decimal("0.00"))

    def test_equal_values_returns_that_value(self) -> None:
        result = effective_sale_discount_percent(
            loyalty_discount=Decimal("10.00"),
            promo_discount=Decimal("10.00"),
        )
        self.assertEqual(result, Decimal("10.00"))


# ---------------------------------------------------------------------------
# build_sale_discount_breakdown
# ---------------------------------------------------------------------------

class BuildSaleDiscountBreakdownTests(unittest.TestCase):

    def test_no_discount_returns_sin_descuento(self) -> None:
        result = build_sale_discount_breakdown(
            loyalty_discount=Decimal("0.00"),
            promo_discount=Decimal("0.00"),
        )
        self.assertEqual(result["winner_source"], "SIN_DESCUENTO")
        self.assertEqual(result["effective_discount"], Decimal("0.00"))

    def test_only_loyalty_returns_lealtad(self) -> None:
        result = build_sale_discount_breakdown(
            loyalty_discount=Decimal("10.00"),
            promo_discount=Decimal("0.00"),
            loyalty_source="Leal",
        )
        self.assertEqual(result["winner_source"], "LEALTAD")
        self.assertIn("10%", result["winner_label"])

    def test_only_promo_returns_promocion_manual(self) -> None:
        result = build_sale_discount_breakdown(
            loyalty_discount=Decimal("0.00"),
            promo_discount=Decimal("20.00"),
        )
        self.assertEqual(result["winner_source"], "PROMOCION_MANUAL")
        self.assertIn("20%", result["winner_label"])

    def test_promo_wins_when_higher(self) -> None:
        result = build_sale_discount_breakdown(
            loyalty_discount=Decimal("10.00"),
            promo_discount=Decimal("25.00"),
        )
        self.assertEqual(result["winner_source"], "PROMOCION_MANUAL")
        self.assertEqual(result["effective_discount"], Decimal("25.00"))

    def test_loyalty_wins_when_higher(self) -> None:
        result = build_sale_discount_breakdown(
            loyalty_discount=Decimal("20.00"),
            promo_discount=Decimal("10.00"),
        )
        self.assertEqual(result["winner_source"], "LEALTAD")
        self.assertEqual(result["effective_discount"], Decimal("20.00"))

    def test_empty_loyalty_source_defaults(self) -> None:
        result = build_sale_discount_breakdown(
            loyalty_discount=Decimal("5.00"),
            promo_discount=Decimal("0.00"),
            loyalty_source="  ",
        )
        self.assertIn("Cliente", result["winner_label"])


# ---------------------------------------------------------------------------
# calculate_sale_totals
# ---------------------------------------------------------------------------

class CalculateSaleTotalsTests(unittest.TestCase):

    def _cart(self, *items):
        return [{"precio_unitario": str(p), "cantidad": c} for p, c in items]

    def test_single_item_no_discount(self) -> None:
        cart = self._cart((Decimal("100.00"), 2))
        subtotal, discount, applied, total = calculate_sale_totals(
            cart, loyalty_discount=0, promo_discount=0
        )
        self.assertEqual(subtotal, Decimal("200.00"))
        self.assertEqual(discount, Decimal("0.00"))
        self.assertEqual(applied, Decimal("0.00"))
        self.assertEqual(total, Decimal("200.00"))

    def test_discount_applied_correctly(self) -> None:
        cart = self._cart((Decimal("100.00"), 1))
        subtotal, discount, applied, total = calculate_sale_totals(
            cart, loyalty_discount=Decimal("10.00"), promo_discount=0
        )
        self.assertEqual(subtotal, Decimal("100.00"))
        self.assertEqual(discount, Decimal("10.00"))
        self.assertEqual(applied, Decimal("10.00"))
        self.assertEqual(total, Decimal("90.00"))

    def test_multiple_items_summed(self) -> None:
        cart = self._cart((Decimal("50.00"), 2), (Decimal("30.00"), 3))
        subtotal, _, _, total = calculate_sale_totals(
            cart, loyalty_discount=0, promo_discount=0
        )
        self.assertEqual(subtotal, Decimal("190.00"))
        self.assertEqual(total, Decimal("190.00"))

    def test_discount_cannot_exceed_subtotal(self) -> None:
        cart = self._cart((Decimal("10.00"), 1))
        _, _, applied, total = calculate_sale_totals(
            cart, loyalty_discount=Decimal("200.00"), promo_discount=0
        )
        # El descuento no puede superar el subtotal
        self.assertGreaterEqual(total, Decimal("0.00"))
        self.assertLessEqual(applied, Decimal("10.00"))


# ---------------------------------------------------------------------------
# calculate_sale_pricing
# ---------------------------------------------------------------------------

class CalculateSalePricingTests(unittest.TestCase):

    def test_returns_sale_pricing_dataclass(self) -> None:
        cart = [{"precio_unitario": "100.00", "cantidad": 1}]
        pricing = calculate_sale_pricing(
            cart, loyalty_discount=Decimal("10.00"), promo_discount=0
        )
        self.assertIsInstance(pricing, SalePricing)
        self.assertEqual(pricing.subtotal, Decimal("100.00"))
        self.assertEqual(pricing.discount_percent, Decimal("10.00"))
        self.assertEqual(pricing.applied_discount, Decimal("10.00"))

    def test_collected_total_includes_rounding(self) -> None:
        # El collected_total puede diferir del total_after_discount por redondeo
        cart = [{"precio_unitario": "99.99", "cantidad": 1}]
        pricing = calculate_sale_pricing(
            cart, loyalty_discount=0, promo_discount=0
        )
        # collected_total = total_after_discount + rounding_adjustment
        self.assertEqual(
            pricing.collected_total,
            pricing.total_after_discount + pricing.rounding_adjustment,
        )


if __name__ == "__main__":
    unittest.main()
