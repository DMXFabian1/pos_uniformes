"""Helpers visibles para el presupuesto en armado."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class QuoteCartRowView:
    values: tuple[object, ...]


@dataclass(frozen=True)
class QuoteCartSummaryView:
    total_label: str
    summary_label: str


@dataclass(frozen=True)
class QuoteCartView:
    rows: tuple[QuoteCartRowView, ...]
    total_items: int
    total: Decimal
    summary: QuoteCartSummaryView


def build_quote_cart_view(quote_cart: list[dict[str, object]]) -> QuoteCartView:
    rows: list[QuoteCartRowView] = []
    total_items = 0
    total = Decimal("0.00")
    for item in quote_cart:
        line_subtotal = Decimal(item["precio_unitario"]) * int(item["cantidad"])
        total_items += int(item["cantidad"])
        total += line_subtotal
        rows.append(
            QuoteCartRowView(
                values=(
                    item["sku"],
                    item["producto_nombre"],
                    item["cantidad"],
                    item["precio_unitario"],
                    line_subtotal,
                )
            )
        )
    normalized_total = total.quantize(Decimal("0.01"))
    return QuoteCartView(
        rows=tuple(rows),
        total_items=total_items,
        total=normalized_total,
        summary=QuoteCartSummaryView(
            total_label=f"${normalized_total}",
            summary_label=(
                f"Lineas: {len(quote_cart)} | Piezas: {total_items} | Total estimado: ${normalized_total}"
                if quote_cart
                else "Presupuesto vacio."
            ),
        ),
    )
