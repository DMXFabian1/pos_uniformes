"""Filas visibles y tonos del listado de Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteTableRowView:
    quote_id: int
    values: tuple[object, ...]
    status_tone: str
    total_tone: str


def build_quote_table_row_views(rows: list[dict[str, object]]) -> tuple[QuoteTableRowView, ...]:
    return tuple(
        QuoteTableRowView(
            quote_id=int(row["id"]),
            values=(
                row["folio"],
                row["cliente"],
                row["estado"],
                row["total"],
                row["usuario"],
                row["vigencia"],
                row["fecha"],
            ),
            status_tone=str(row["status_tone"]),
            total_tone="positive",
        )
        for row in rows
    )
