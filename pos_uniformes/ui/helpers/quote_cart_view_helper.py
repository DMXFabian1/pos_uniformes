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
    school_summary_label: str


@dataclass(frozen=True)
class QuoteCartView:
    rows: tuple[QuoteCartRowView, ...]
    total_items: int
    total: Decimal
    summary: QuoteCartSummaryView
    school_options: tuple[str, ...]


def build_quote_cart_view(quote_cart: list[dict[str, object]], *, school_filter: str = "") -> QuoteCartView:
    rows: list[QuoteCartRowView] = []
    total_items = 0
    total = Decimal("0.00")
    normalized_school_filter = school_filter.strip()
    school_totals: dict[str, int] = {}
    visible_quote_cart = [
        item
        for item in quote_cart
        if not normalized_school_filter or str(item.get("escuela_nombre", "General")) == normalized_school_filter
    ]
    for item in quote_cart:
        school_name = str(item.get("escuela_nombre") or "General")
        school_totals[school_name] = school_totals.get(school_name, 0) + int(item["cantidad"])
    for item in visible_quote_cart:
        line_subtotal = Decimal(item["precio_unitario"]) * int(item["cantidad"])
        total_items += int(item["cantidad"])
        total += line_subtotal
        rows.append(
            QuoteCartRowView(
                values=(
                    item["sku"],
                    item.get("nivel_educativo_nombre") or "Sin nivel",
                    item.get("escuela_nombre") or "General",
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
                f"Lineas: {len(visible_quote_cart)} | Piezas: {total_items} | Total estimado: ${normalized_total}"
                if visible_quote_cart
                else "Presupuesto vacio."
            ),
            school_summary_label=(
                " | ".join(
                    f"{school_name} ({pieces})"
                    for school_name, pieces in sorted(school_totals.items())
                )
                if school_totals
                else "Sin escuelas activas."
            ),
        ),
        school_options=tuple(sorted(school_totals)),
    )
