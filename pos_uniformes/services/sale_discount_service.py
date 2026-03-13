"""Reglas puras para descuentos en caja."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def normalize_discount_value(value: object | None) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def format_discount_label(value: Decimal | str | int | float) -> str:
    normalized = normalize_discount_value(value)
    if normalized == normalized.quantize(Decimal("1")):
        return f"{int(normalized)}%"
    return f"{format(normalized, '.2f').rstrip('0').rstrip('.')}%"


def effective_sale_discount_percent(
    *,
    loyalty_discount: Decimal | str | int | float,
    promo_discount: Decimal | str | int | float,
) -> Decimal:
    return max(
        normalize_discount_value(loyalty_discount),
        normalize_discount_value(promo_discount),
    )


def build_sale_discount_breakdown(
    *,
    loyalty_discount: Decimal | str | int | float,
    promo_discount: Decimal | str | int | float,
    loyalty_source: str = "Cliente",
) -> dict[str, object]:
    normalized_loyalty = normalize_discount_value(loyalty_discount)
    normalized_promo = normalize_discount_value(promo_discount)
    effective_discount = effective_sale_discount_percent(
        loyalty_discount=normalized_loyalty,
        promo_discount=normalized_promo,
    )
    normalized_source = loyalty_source.strip() or "Cliente"

    if normalized_loyalty > Decimal("0.00") and normalized_promo > Decimal("0.00"):
        if normalized_promo > normalized_loyalty:
            winner_source = "PROMOCION_MANUAL"
            winner_label = f"Promocion manual {format_discount_label(normalized_promo)}"
        else:
            winner_source = "LEALTAD"
            winner_label = f"Lealtad {normalized_source} {format_discount_label(normalized_loyalty)}"
    elif normalized_loyalty > Decimal("0.00"):
        winner_source = "LEALTAD"
        winner_label = f"Lealtad {normalized_source} {format_discount_label(normalized_loyalty)}"
    elif normalized_promo > Decimal("0.00"):
        winner_source = "PROMOCION_MANUAL"
        winner_label = f"Promocion manual {format_discount_label(normalized_promo)}"
    else:
        winner_source = "SIN_DESCUENTO"
        winner_label = "Sin descuento"

    return {
        "loyalty_discount": normalized_loyalty,
        "promo_discount": normalized_promo,
        "effective_discount": effective_discount,
        "loyalty_source": normalized_source,
        "winner_source": winner_source,
        "winner_label": winner_label,
    }


def calculate_sale_totals(
    sale_cart: list[dict[str, object]],
    *,
    loyalty_discount: Decimal | str | int | float,
    promo_discount: Decimal | str | int | float,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    subtotal = Decimal("0.00")
    for item in sale_cart:
        subtotal += Decimal(item["precio_unitario"]) * int(item["cantidad"])
    discount_percent = effective_sale_discount_percent(
        loyalty_discount=loyalty_discount,
        promo_discount=promo_discount,
    )
    applied_discount = (subtotal * discount_percent / Decimal("100.00")).quantize(Decimal("0.01"))
    if applied_discount > subtotal:
        applied_discount = subtotal
    total = subtotal - applied_discount
    return subtotal, discount_percent, applied_discount, total
