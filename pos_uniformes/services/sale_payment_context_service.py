"""Contexto operativo de cobro para notas y cierre de venta."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from pos_uniformes.services.sale_note_service import build_sale_note_parts
from pos_uniformes.services.sale_payment_note_service import SalePaymentDetails


@dataclass(frozen=True)
class SalePaymentNoteContext:
    payment_method: str
    note_parts: tuple[str, ...]


def build_sale_payment_note_context(
    *,
    payment_method: str,
    discount_percent: Decimal | str | int | float,
    applied_discount: Decimal | str | int | float,
    rounding_adjustment: Decimal | str | int | float,
    breakdown: dict[str, object],
    format_discount_label: Callable[[Decimal | str | int | float], str],
    payment_details: SalePaymentDetails,
) -> SalePaymentNoteContext:
    normalized_payment_method = (payment_method or "").strip() or "Efectivo"
    note_parts = build_sale_note_parts(
        payment_method=normalized_payment_method,
        discount_percent=discount_percent,
        applied_discount=applied_discount,
        rounding_adjustment=rounding_adjustment,
        breakdown=breakdown,
        format_discount_label=format_discount_label,
        extra_notes=list(payment_details.note_lines),
    )
    return SalePaymentNoteContext(
        payment_method=normalized_payment_method,
        note_parts=tuple(note_parts),
    )
