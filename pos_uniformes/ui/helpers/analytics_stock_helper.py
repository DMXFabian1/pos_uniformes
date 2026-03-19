"""Filas visibles y tonos de stock critico para Analytics."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.utils.product_name import sanitize_product_display_name


@dataclass(frozen=True)
class AnalyticsStockRowView:
    values: tuple[object, object, object, object, object]
    stock_tone: str
    reserved_tone: str
    state_tone: str


def build_analytics_stock_row_views(rows: list[object] | tuple[object, ...]) -> tuple[AnalyticsStockRowView, ...]:
    row_views: list[AnalyticsStockRowView] = []
    for row in rows:
        stock_value = int(getattr(row, "stock_actual", 0) or 0)
        reserved_value = int(getattr(row, "reserved_quantity", 0) or 0)
        is_active = bool(getattr(row, "is_active", False))
        row_views.append(
            AnalyticsStockRowView(
                values=(
                    getattr(row, "sku", ""),
                    sanitize_product_display_name(getattr(row, "product_name", "")),
                    stock_value,
                    reserved_value,
                    "ACTIVA" if is_active else "INACTIVA",
                ),
                stock_tone="danger" if stock_value == 0 else "warning" if stock_value <= 3 else "positive",
                reserved_tone="warning" if reserved_value > 0 else "muted",
                state_tone="positive" if is_active else "muted",
            )
        )
    return tuple(row_views)
