"""Helpers puros para el resumen visible de caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SaleCashierSummary:
    total_label: str
    meta_label: str
    summary_label: str


def build_sale_cashier_summary(
    *,
    has_items: bool,
    lines_count: int,
    total_items: int,
    subtotal: Decimal,
    applied_discount: Decimal,
    rounding_adjustment: Decimal,
    collected_total: Decimal,
    payment_method: str,
    winner_label: str,
) -> SaleCashierSummary:
    if not has_items:
        return SaleCashierSummary(
            total_label="$0.00",
            meta_label="Total a cobrar",
            summary_label="Carrito vacio.",
        )

    summary_label = (
        f"Lineas: {lines_count} | Piezas: {total_items} | "
        f"Subtotal: ${subtotal} | Descuento: ${applied_discount}"
    )
    if rounding_adjustment != Decimal("0.00"):
        summary_label += f" | Ajuste: ${rounding_adjustment}"

    return SaleCashierSummary(
        total_label=f"${collected_total}",
        meta_label=f"{payment_method} | {winner_label}",
        summary_label=summary_label,
    )
