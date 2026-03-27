"""Helpers visibles para el lote de conteo fisico."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.services.inventory_count_service import InventoryCountRow, build_inventory_count_summary


@dataclass(frozen=True)
class InventoryCountTableRowView:
    values: tuple[object, ...]
    variante_id: int


@dataclass(frozen=True)
class InventoryCountBatchView:
    rows: tuple[InventoryCountTableRowView, ...]
    summary_label: str
    status_label: str
    confirmation_lines: tuple[str, ...]


def build_inventory_count_batch_view(rows: list[InventoryCountRow]) -> InventoryCountBatchView:
    summary = build_inventory_count_summary(rows)
    table_rows = tuple(
        InventoryCountTableRowView(
            values=(
                row.sku,
                row.producto_nombre,
                row.stock_sistema,
                row.stock_contado,
                _format_delta_label(row.delta),
            ),
            variante_id=int(row.variante_id),
        )
        for row in rows
    )

    if not rows:
        return InventoryCountBatchView(
            rows=(),
            summary_label="Lote vacio.",
            status_label="Escanea un SKU y agrega el conteo al lote.",
            confirmation_lines=(),
        )

    summary_label = (
        f"Filas con diferencia: {summary.changed_rows} | "
        f"Suben: {summary.increases} | "
        f"Bajan: {summary.decreases}"
    )
    if summary.zero_rows:
        summary_label += f" | Sin cambio: {summary.zero_rows}"

    confirmation_lines = (
        f"Filas capturadas: {len(rows)}",
        f"Filas con diferencia: {summary.changed_rows}",
        f"Suben: {summary.increases}",
        f"Bajan: {summary.decreases}",
    )
    if summary.zero_rows:
        confirmation_lines += (f"Sin cambio: {summary.zero_rows}",)

    return InventoryCountBatchView(
        rows=table_rows,
        summary_label=summary_label,
        status_label="Revisa el lote antes de aplicar. Solo se guardaran filas con diferencia.",
        confirmation_lines=confirmation_lines,
    )


def _format_delta_label(delta: int) -> str:
    if delta > 0:
        return f"+{delta}"
    return str(delta)
