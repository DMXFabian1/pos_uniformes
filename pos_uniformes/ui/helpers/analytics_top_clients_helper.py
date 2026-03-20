"""Filas visibles y tonos de top clientes para Analytics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyticsTopClientRowView:
    values: tuple[object, object, object, object]
    sales_tone: str
    amount_tone: str
    row_tone: str | None


def build_analytics_top_client_row_views(rows: list[object] | tuple[object, ...]) -> tuple[AnalyticsTopClientRowView, ...]:
    return tuple(
        AnalyticsTopClientRowView(
            values=(
                getattr(row, "client_name", ""),
                getattr(row, "client_code", ""),
                getattr(row, "sales_count", 0),
                getattr(row, "amount", 0),
            ),
            sales_tone="positive" if row_index == 0 else "positive" if int(getattr(row, "sales_count", 0) or 0) >= 2 else "warning",
            amount_tone="positive" if row_index == 0 else "warning",
            row_tone="positive" if row_index == 0 else None,
        )
        for row_index, row in enumerate(rows)
    )
