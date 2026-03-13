"""Helpers puros para mostrar totales coherentes en tickets de venta."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SaleTicketTotals:
    subtotal: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    total: Decimal


def resolve_sale_ticket_totals(
    *,
    subtotal: Decimal | str | int | float,
    stored_discount_percent: Decimal | str | int | float | None,
    stored_discount_amount: Decimal | str | int | float | None,
    total: Decimal | str | int | float,
) -> SaleTicketTotals:
    normalized_subtotal = Decimal(str(subtotal or 0)).quantize(Decimal("0.01"))
    normalized_total = Decimal(str(total or 0)).quantize(Decimal("0.01"))
    normalized_discount_percent = Decimal(str(stored_discount_percent or 0)).quantize(Decimal("0.01"))
    normalized_discount_amount = Decimal(str(stored_discount_amount or 0)).quantize(Decimal("0.01"))

    inferred_discount_amount = (normalized_subtotal - normalized_total).quantize(Decimal("0.01"))
    if inferred_discount_amount < Decimal("0.00"):
        inferred_discount_amount = Decimal("0.00")

    if normalized_discount_amount <= Decimal("0.00") and inferred_discount_amount > Decimal("0.00"):
        normalized_discount_amount = inferred_discount_amount
        if normalized_subtotal > Decimal("0.00"):
            normalized_discount_percent = (
                normalized_discount_amount * Decimal("100.00") / normalized_subtotal
            ).quantize(Decimal("0.01"))
        else:
            normalized_discount_percent = Decimal("0.00")

    return SaleTicketTotals(
        subtotal=normalized_subtotal,
        discount_percent=normalized_discount_percent,
        discount_amount=normalized_discount_amount,
        total=normalized_total,
    )
