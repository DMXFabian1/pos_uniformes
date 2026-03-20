"""Filas visibles de top productos para Analytics."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.utils.product_name import sanitize_product_display_name


@dataclass(frozen=True)
class AnalyticsTopProductRowView:
    values: tuple[object, object, object, object]
    units_tone: str
    revenue_tone: str
    row_tone: str | None


def build_analytics_top_product_rows(rows: list[object] | tuple[object, ...]) -> tuple[AnalyticsTopProductRowView, ...]:
    return tuple(
        AnalyticsTopProductRowView(
            values=(
                getattr(row, "sku", ""),
                sanitize_product_display_name(getattr(row, "product_name", "")),
                getattr(row, "units_sold", 0),
                getattr(row, "revenue", 0),
            ),
            units_tone="positive" if row_index == 0 else "warning",
            revenue_tone="positive" if row_index == 0 else "warning",
            row_tone="positive" if row_index == 0 else None,
        )
        for row_index, row in enumerate(rows)
    )
