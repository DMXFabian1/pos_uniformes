"""Helpers puros para redondeo de cobro."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR


@dataclass(frozen=True)
class SaleRoundingResult:
    total_after_discount: Decimal
    rounding_adjustment: Decimal
    collected_total: Decimal


def resolve_sale_rounding(
    total_after_discount: Decimal | str | int | float,
) -> SaleRoundingResult:
    normalized_total = Decimal(str(total_after_discount or 0)).quantize(Decimal("0.01"))
    if normalized_total < Decimal("0.00"):
        raise ValueError("El total para redondeo no puede ser negativo.")

    integer_part = normalized_total.to_integral_value(rounding=ROUND_FLOOR)
    cents = (normalized_total - integer_part).quantize(Decimal("0.01"))

    if cents <= Decimal("0.19"):
        rounded_total = integer_part
    elif cents <= Decimal("0.69"):
        rounded_total = (integer_part + Decimal("0.50")).quantize(Decimal("0.01"))
    else:
        rounded_total = (integer_part + Decimal("1.00")).quantize(Decimal("0.01"))

    rounding_adjustment = (rounded_total - normalized_total).quantize(Decimal("0.01"))
    return SaleRoundingResult(
        total_after_discount=normalized_total,
        rounding_adjustment=rounding_adjustment,
        collected_total=rounded_total,
    )
