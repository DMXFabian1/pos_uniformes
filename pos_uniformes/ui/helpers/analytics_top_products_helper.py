"""Filas visibles de top productos para Analytics."""

from __future__ import annotations

from pos_uniformes.utils.product_name import sanitize_product_display_name


def build_analytics_top_product_rows(rows: list[object] | tuple[object, ...]) -> tuple[tuple[object, object, object, object], ...]:
    return tuple(
        (
            getattr(row, "sku", ""),
            sanitize_product_display_name(getattr(row, "product_name", "")),
            getattr(row, "units_sold", 0),
            getattr(row, "revenue", 0),
        )
        for row in rows
    )
