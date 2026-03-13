from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_rounding_service import resolve_sale_rounding


class SaleRoundingServiceTests(unittest.TestCase):
    def test_keeps_exact_total_when_cents_are_zero(self) -> None:
        result = resolve_sale_rounding(Decimal("179.00"))

        self.assertEqual(result.total_after_discount, Decimal("179.00"))
        self.assertEqual(result.rounding_adjustment, Decimal("0.00"))
        self.assertEqual(result.collected_total, Decimal("179.00"))

    def test_rounds_down_until_point_nineteen(self) -> None:
        result = resolve_sale_rounding(Decimal("179.19"))

        self.assertEqual(result.rounding_adjustment, Decimal("-0.19"))
        self.assertEqual(result.collected_total, Decimal("179.00"))

    def test_rounds_up_to_point_fifty_from_point_twenty(self) -> None:
        result = resolve_sale_rounding(Decimal("179.20"))

        self.assertEqual(result.rounding_adjustment, Decimal("0.30"))
        self.assertEqual(result.collected_total, Decimal("179.50"))

    def test_rounds_down_to_point_fifty_until_point_sixty_nine(self) -> None:
        result = resolve_sale_rounding(Decimal("179.69"))

        self.assertEqual(result.rounding_adjustment, Decimal("-0.19"))
        self.assertEqual(result.collected_total, Decimal("179.50"))

    def test_rounds_up_to_next_peso_from_point_seventy(self) -> None:
        result = resolve_sale_rounding(Decimal("179.70"))

        self.assertEqual(result.rounding_adjustment, Decimal("0.30"))
        self.assertEqual(result.collected_total, Decimal("180.00"))

    def test_raises_for_negative_totals(self) -> None:
        with self.assertRaisesRegex(ValueError, "no puede ser negativo"):
            resolve_sale_rounding(Decimal("-1.00"))


if __name__ == "__main__":
    unittest.main()
