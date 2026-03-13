from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.manual_promo_flow_service import (
    apply_manual_promo_authorization,
    current_manual_promo_percent,
)
from pos_uniformes.services.sale_client_discount_service import resolve_sale_client_discount
from pos_uniformes.services.sale_discount_lock_service import (
    build_sale_discount_lock_state,
    build_sale_discount_lock_tooltip,
)
from pos_uniformes.services.sale_discount_service import (
    build_sale_discount_breakdown,
    effective_sale_discount_percent,
    format_discount_label,
    normalize_discount_value,
)


class SaleClientDiscountFlowTests(unittest.TestCase):
    def test_client_preferred_discount_wins_over_loyalty_discount(self) -> None:
        client_discount = resolve_sale_client_discount(
            preferred_discount=Decimal("12.50"),
            loyalty_discount=Decimal("10.00"),
            normalize_discount_value=normalize_discount_value,
        )
        lock_state = build_sale_discount_lock_state(
            locked=True,
            discount_percent=client_discount,
            source_label="Cliente VIP",
            normalize_discount_value=normalize_discount_value,
        )

        self.assertEqual(client_discount, Decimal("12.50"))
        self.assertTrue(lock_state.locked)
        self.assertEqual(lock_state.discount_percent, Decimal("12.50"))
        self.assertEqual(
            build_sale_discount_lock_tooltip(
                state=lock_state,
                format_discount_label=format_discount_label,
            ),
            "Promocion manual separada del beneficio de lealtad. Cliente actual: Cliente VIP (12.5%). No se acumula; se aplicara el mayor beneficio.",
        )

    def test_manual_promo_does_not_accumulate_when_client_benefit_is_higher(self) -> None:
        client_discount = resolve_sale_client_discount(
            preferred_discount=Decimal("0.00"),
            loyalty_discount=Decimal("15.00"),
            normalize_discount_value=normalize_discount_value,
        )
        promo_state = apply_manual_promo_authorization(Decimal("10.00"))
        promo_discount = current_manual_promo_percent(
            selected_percent=Decimal("10.00"),
            state=promo_state,
        )
        effective_discount = effective_sale_discount_percent(
            loyalty_discount=client_discount,
            promo_discount=promo_discount,
        )
        breakdown = build_sale_discount_breakdown(
            loyalty_discount=client_discount,
            promo_discount=promo_discount,
            loyalty_source="Leal",
        )

        self.assertEqual(client_discount, Decimal("15.00"))
        self.assertEqual(promo_discount, Decimal("10.00"))
        self.assertEqual(effective_discount, Decimal("15.00"))
        self.assertEqual(breakdown["winner_source"], "LEALTAD")
        self.assertEqual(breakdown["winner_label"], "Lealtad Leal 15%")

    def test_manual_promo_overrides_client_benefit_when_it_is_higher(self) -> None:
        client_discount = resolve_sale_client_discount(
            preferred_discount=Decimal("0.00"),
            loyalty_discount=Decimal("10.00"),
            normalize_discount_value=normalize_discount_value,
        )
        promo_state = apply_manual_promo_authorization(Decimal("20.00"))
        promo_discount = current_manual_promo_percent(
            selected_percent=Decimal("20.00"),
            state=promo_state,
        )
        effective_discount = effective_sale_discount_percent(
            loyalty_discount=client_discount,
            promo_discount=promo_discount,
        )
        breakdown = build_sale_discount_breakdown(
            loyalty_discount=client_discount,
            promo_discount=promo_discount,
            loyalty_source="Leal",
        )

        self.assertEqual(effective_discount, Decimal("20.00"))
        self.assertEqual(breakdown["winner_source"], "PROMOCION_MANUAL")
        self.assertEqual(breakdown["winner_label"], "Promocion manual 20%")
