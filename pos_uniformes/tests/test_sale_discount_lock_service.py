from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_discount_lock_service import (
    build_sale_discount_lock_state,
    build_sale_discount_lock_tooltip,
)
from pos_uniformes.services.sale_discount_service import format_discount_label, normalize_discount_value


class SaleDiscountLockServiceTests(unittest.TestCase):
    def test_build_sale_discount_lock_state_normalizes_values(self) -> None:
        state = build_sale_discount_lock_state(
            locked=True,
            discount_percent="10",
            source_label="  LEAL  ",
            normalize_discount_value=normalize_discount_value,
        )

        self.assertTrue(state.locked)
        self.assertEqual(state.discount_percent, Decimal("10.00"))
        self.assertEqual(state.source_label, "LEAL")

    def test_build_sale_discount_lock_tooltip_for_locked_state(self) -> None:
        state = build_sale_discount_lock_state(
            locked=True,
            discount_percent=Decimal("12.50"),
            source_label="Profesor",
            normalize_discount_value=normalize_discount_value,
        )

        tooltip = build_sale_discount_lock_tooltip(
            state=state,
            format_discount_label=format_discount_label,
        )

        self.assertEqual(
            tooltip,
            "Promocion manual separada del beneficio de lealtad. Cliente actual: Profesor (12.5%). No se acumula; se aplicara el mayor beneficio.",
        )

    def test_build_sale_discount_lock_tooltip_for_unlocked_state(self) -> None:
        state = build_sale_discount_lock_state(
            locked=False,
            discount_percent=Decimal("0.00"),
            source_label="",
            normalize_discount_value=normalize_discount_value,
        )

        tooltip = build_sale_discount_lock_tooltip(
            state=state,
            format_discount_label=format_discount_label,
        )

        self.assertEqual(
            tooltip,
            "Aplica una promocion manual no acumulable. Si hay lealtad, se aplicara el mayor beneficio.",
        )
