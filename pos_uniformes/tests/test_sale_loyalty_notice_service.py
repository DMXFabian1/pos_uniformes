from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_discount_service import format_discount_label
from pos_uniformes.services.sale_loyalty_notice_service import build_sale_loyalty_transition_notice


class SaleLoyaltyNoticeServiceTests(unittest.TestCase):
    def test_notice_describes_level_change(self) -> None:
        notice = build_sale_loyalty_transition_notice(
            client_name="Maria",
            previous_label="Basico",
            new_label="Leal",
            new_discount=Decimal("10.00"),
            format_discount_label=format_discount_label,
        )

        self.assertEqual(
            notice,
            "Maria cambia de Basico a Leal. El nuevo descuento de 10% aplicara desde la siguiente compra.",
        )

    def test_notice_describes_same_level_with_existing_discount(self) -> None:
        notice = build_sale_loyalty_transition_notice(
            client_name="",
            previous_label="Leal",
            new_label="Leal",
            new_discount=Decimal("12.50"),
            format_discount_label=format_discount_label,
        )

        self.assertEqual(
            notice,
            "Este cliente conserva el nivel Leal. Su descuento vigente de 12.5% seguira aplicando en la siguiente compra.",
        )
