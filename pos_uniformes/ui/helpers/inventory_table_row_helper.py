"""Filas visibles y tonos de la tabla de Inventario."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InventoryTableRowView:
    variant_id: int
    values: tuple[object, ...]
    stock_tone: str
    committed_tone: str | None
    status_tone: str
    qr_tone: str


def build_inventory_table_row_views(visible_rows: list[dict[str, object]]) -> tuple[InventoryTableRowView, ...]:
    return tuple(build_inventory_table_row_view(row) for row in visible_rows)


def build_inventory_table_row_view(row: dict[str, object]) -> InventoryTableRowView:
    stock_value = int(row["stock_actual"])
    committed_value = int(row["apartado_cantidad"])
    stock_tone = "danger" if stock_value == 0 else "warning" if stock_value <= 3 else "positive"
    status_text = "ACTIVA" if row["variante_activa"] else "INACTIVA"
    status_tone = "positive" if row["variante_activa"] else "muted"
    qr_text = "Listo" if row["qr_exists"] else "Pendiente"
    qr_tone = "positive" if row["qr_exists"] else "warning"
    return InventoryTableRowView(
        variant_id=int(row["variante_id"]),
        values=(
            row["sku"],
            row["producto_nombre_base"],
            row["talla"],
            row["color"],
            _build_stock_table_text(stock_value),
            committed_value,
            status_text,
            qr_text,
        ),
        stock_tone=stock_tone,
        committed_tone="warning" if committed_value > 0 else None,
        status_tone=status_tone,
        qr_tone=qr_tone,
    )


def _build_stock_table_text(stock_value: int) -> str:
    if stock_value == 0:
        return "0 Agotado"
    if stock_value <= 3:
        return f"{stock_value} Bajo"
    return f"{stock_value} OK"
