"""Helpers puros para resolver el beneficio visible de un cliente en caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from pos_uniformes.services.loyalty_service import LoyaltyService
from pos_uniformes.services.sale_client_discount_service import resolve_sale_client_discount


@dataclass(frozen=True)
class SaleClientBenefit:
    discount_percent: Decimal
    source_label: str


def resolve_sale_client_benefit(
    *,
    preferred_discount: Decimal | str | int | float | None,
    loyalty_level: object | None,
    loyalty_discount_resolver: Callable[[object | None], Decimal],
    normalize_discount_value: Callable[[object | None], Decimal],
) -> SaleClientBenefit:
    visual = LoyaltyService.visual_spec(loyalty_level)
    discount_percent = resolve_sale_client_discount(
        preferred_discount=preferred_discount,
        loyalty_discount=loyalty_discount_resolver(loyalty_level),
        normalize_discount_value=normalize_discount_value,
    )
    return SaleClientBenefit(
        discount_percent=discount_percent,
        source_label=visual.label.strip() or "Cliente",
    )
