from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_discount_option_service import (
    build_sale_discount_options,
    expected_discount_option_label,
)
from pos_uniformes.services.sale_discount_service import format_discount_label, normalize_discount_value


class SaleDiscountOptionServiceTests(unittest.TestCase):
    def test_build_sale_discount_options_deduplicates_values_and_keeps_manual_current(self) -> None:
        options = build_sale_discount_options(
            preset_values=[Decimal("5.00"), Decimal("10.00"), Decimal("10.0")],
            current_discount=Decimal("12.50"),
            normalize_discount_value=normalize_discount_value,
            format_discount_label=format_discount_label,
        )

        self.assertEqual(
            options,
            [
                ("Sin descuento", Decimal("0.00")),
                ("5%", Decimal("5.00")),
                ("10%", Decimal("10.00")),
                ("Manual (12.5%)", Decimal("12.50")),
            ],
        )

    def test_build_sale_discount_options_skips_manual_when_current_is_zero(self) -> None:
        options = build_sale_discount_options(
            preset_values=[Decimal("5.00")],
            current_discount=Decimal("0.00"),
            normalize_discount_value=normalize_discount_value,
            format_discount_label=format_discount_label,
        )

        self.assertEqual(
            options,
            [
                ("Sin descuento", Decimal("0.00")),
                ("5%", Decimal("5.00")),
            ],
        )

    def test_expected_discount_option_label_matches_zero_and_non_zero_cases(self) -> None:
        self.assertEqual(
            expected_discount_option_label(
                Decimal("0.00"),
                normalize_discount_value=normalize_discount_value,
                format_discount_label=format_discount_label,
            ),
            "Sin descuento",
        )
        self.assertEqual(
            expected_discount_option_label(
                Decimal("12.50"),
                normalize_discount_value=normalize_discount_value,
                format_discount_label=format_discount_label,
            ),
            "12.5%",
        )
