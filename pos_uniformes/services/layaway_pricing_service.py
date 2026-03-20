"""Pricing compartido para apartados con beneficio de cliente."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.services.sale_rounding_service import resolve_sale_rounding
from pos_uniformes.services.sale_discount_service import normalize_discount_value
from pos_uniformes.services.sale_selected_client_service import load_sale_selected_client_discount_percent

LAYAWAY_MIN_DEPOSIT_PERCENT = Decimal("20.00")


@dataclass(frozen=True)
class LayawayPricing:
    subtotal: Decimal
    rounding_adjustment: Decimal
    total: Decimal


def resolve_layaway_client_discount_percent(
    session,
    *,
    selected_client_id: int | str | None,
) -> Decimal:
    return normalize_discount_value(
        load_sale_selected_client_discount_percent(
            session,
            selected_client_id=selected_client_id,
            normalize_discount_value=normalize_discount_value,
        )
    )


def resolve_layaway_unit_price(
    base_price: Decimal | str | int | float,
    *,
    discount_percent: Decimal | str | int | float,
) -> Decimal:
    normalized_price = Decimal(str(base_price or 0)).quantize(Decimal("0.01"))
    normalized_discount = normalize_discount_value(discount_percent)
    if normalized_discount <= Decimal("0.00"):
        return normalized_price
    discounted_price = (
        normalized_price * (Decimal("100.00") - normalized_discount) / Decimal("100.00")
    ).quantize(Decimal("0.01"))
    if discounted_price < Decimal("0.00"):
        return Decimal("0.00")
    return discounted_price


def build_layaway_pricing(total_amount: Decimal | str | int | float) -> LayawayPricing:
    normalized_total = Decimal(str(total_amount or 0)).quantize(Decimal("0.01"))
    rounding = resolve_sale_rounding(normalized_total)
    return LayawayPricing(
        subtotal=rounding.total_after_discount,
        rounding_adjustment=rounding.rounding_adjustment,
        total=rounding.collected_total,
    )


def resolve_layaway_min_deposit(total_amount: Decimal | str | int | float) -> Decimal:
    normalized_total = Decimal(str(total_amount or 0)).quantize(Decimal("0.01"))
    if normalized_total <= Decimal("0.00"):
        return Decimal("0.00")
    return (normalized_total * LAYAWAY_MIN_DEPOSIT_PERCENT / Decimal("100.00")).quantize(Decimal("0.01"))
