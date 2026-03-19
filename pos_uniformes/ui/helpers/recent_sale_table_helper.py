"""Filas visibles de la tabla de ventas recientes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecentSaleTableRowView:
    sale_id: int
    values: tuple[object, object, object, object, object, object, object]


def build_recent_sale_table_row_views(rows: list[object] | tuple[object, ...]) -> tuple[RecentSaleTableRowView, ...]:
    return tuple(
        RecentSaleTableRowView(
            sale_id=int(getattr(row, "sale_id")),
            values=tuple(getattr(row, "values")),
        )
        for row in rows
    )
