"""Helpers puros para resolver el descuento efectivo del cliente en caja."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable


def resolve_sale_client_discount(
    *,
    preferred_discount: Decimal | str | int | float | None,
    loyalty_discount: Decimal | str | int | float | None,
    normalize_discount_value: Callable[[object | None], Decimal],
) -> Decimal:
    normalized_preferred = normalize_discount_value(preferred_discount)
    if normalized_preferred > Decimal("0.00"):
        return normalized_preferred
    return normalize_discount_value(loyalty_discount)
