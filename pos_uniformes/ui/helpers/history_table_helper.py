"""Helpers visibles para la tabla de Historial."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HistoryTableRowView:
    values: tuple[object, ...]
    source_tone: str
    type_tone: str


def build_history_table_rows(rows: list[dict[str, object]]) -> tuple[HistoryTableRowView, ...]:
    sorted_rows = sorted(
        rows,
        key=lambda item: item["fecha"] or datetime.min,
        reverse=True,
    )[:200]
    return tuple(
        HistoryTableRowView(
            values=(
                row["fecha"].strftime("%d/%m/%Y %H:%M") if row["fecha"] else "",
                row["origen"],
                row["registro"],
                row["tipo"],
                row["cambio"],
                row["resultado"],
                row["usuario"],
                row["detalle"],
            ),
            source_tone="positive" if row["origen"] == "Inventario" else "warning",
            type_tone=_resolve_history_type_tone(str(row["tipo"])),
        )
        for row in sorted_rows
    )


def _resolve_history_type_tone(type_text: str) -> str:
    if "ELIMINACION" in type_text or "SALIDA" in type_text:
        return "danger"
    if "ESTADO" in type_text or "AJUSTE" in type_text:
        return "warning"
    if "CREACION" in type_text or "ENTRADA" in type_text or "RESERVA" in type_text:
        return "positive"
    return "muted"
