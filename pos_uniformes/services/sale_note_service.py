"""Helpers puros para armar notas operativas de la venta."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable


def build_sale_note_parts(
    *,
    payment_method: str,
    discount_percent: Decimal | str | int | float,
    applied_discount: Decimal | str | int | float,
    breakdown: dict[str, object],
    format_discount_label: Callable[[Decimal | str | int | float], str],
    extra_notes: list[object] | None = None,
) -> list[str]:
    note_parts = [f"Metodo de pago: {payment_method}"]

    loyalty_discount = Decimal(str(breakdown.get("loyalty_discount") or 0)).quantize(Decimal("0.01"))
    promo_discount = Decimal(str(breakdown.get("promo_discount") or 0)).quantize(Decimal("0.01"))
    loyalty_source = str(breakdown.get("loyalty_source") or "")
    winner_label = str(breakdown.get("winner_label") or "")
    normalized_applied_discount = Decimal(str(applied_discount or 0)).quantize(Decimal("0.01"))

    note_parts.append(f"Descuento: {discount_percent}%")
    if loyalty_discount > Decimal("0.00"):
        note_parts.append(
            f"Lealtad {loyalty_source}: {format_discount_label(loyalty_discount)}"
        )
    if promo_discount > Decimal("0.00"):
        note_parts.append(
            f"Promocion manual: {format_discount_label(promo_discount)}"
        )
        note_parts.append("Promocion manual autorizada con codigo")
    note_parts.append(f"Beneficio aplicado: {winner_label}")
    if normalized_applied_discount > Decimal("0.00"):
        note_parts.append(f"Descuento aplicado: {normalized_applied_discount}")

    for note in extra_notes or []:
        note_parts.append(str(note))
    return note_parts
