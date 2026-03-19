"""Filas visibles y tonos del listado de Apartados."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LayawayTableRowView:
    layaway_id: int
    values: tuple[object, ...]
    status_tone: str
    balance_tone: str
    due_tone: str


def build_layaway_table_row_views(rows: list[dict[str, object]]) -> tuple[LayawayTableRowView, ...]:
    return tuple(
        LayawayTableRowView(
            layaway_id=int(row["id"]),
            values=(
                row["folio"],
                row["cliente"],
                row["estado"],
                row["total"],
                row["abonado"],
                row["saldo"],
                row["due_text"],
            ),
            status_tone=str(row["status_tone"]),
            balance_tone="positive" if Decimal(row["saldo"]) == Decimal("0.00") else "warning",
            due_tone=str(row["due_tone"]),
        )
        for row in rows
    )
