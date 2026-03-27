"""Helpers visibles para la tabla de Historial."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos_uniformes.utils.date_format import format_display_datetime


@dataclass(frozen=True)
class HistoryTableRowView:
    source_row: dict[str, object]
    values: tuple[object, ...]
    row_tone: str
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
            source_row={
                **row,
                "fecha_label": format_display_datetime(row["fecha"], empty=""),
                "cambio_label": str(row["cambio"]) if row["cambio"] is not None else "—",
                "resultado_label": str(row["resultado"]) if row["resultado"] is not None else "—",
            },
            values=(
                format_display_datetime(row["fecha"], empty=""),
                row["origen"],
                row["registro"],
                row["tipo"],
                row["cambio"],
                row["resultado"],
                row["usuario"],
                row["detalle"],
            ),
            row_tone=_resolve_history_row_tone(str(row["tipo"])),
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


def _resolve_history_row_tone(type_text: str) -> str:
    if "CANCELACION" in type_text or "SALIDA" in type_text or "ELIMINACION" in type_text:
        return "danger"
    if "AJUSTE" in type_text or "ESTADO" in type_text:
        return "warning"
    if "RESERVA" in type_text:
        return "accent"
    if "ENTRADA" in type_text or "CREACION" in type_text:
        return "positive"
    return "muted"
