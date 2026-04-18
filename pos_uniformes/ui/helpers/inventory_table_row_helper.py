"""Filas visibles y tonos de la tabla de Inventario."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class InventoryTableRowView:
    variant_id: int
    values: tuple[object, ...]
    row_tone: str | None
    stock_tone: str
    committed_tone: str | None
    status_tone: str
    qr_tone: str


def build_inventory_table_row_views(visible_rows: list[dict[str, object]]) -> tuple[InventoryTableRowView, ...]:
    return tuple(build_inventory_table_row_view(row) for row in visible_rows)


def build_inventory_table_row_view(row: dict[str, object]) -> InventoryTableRowView:
    stock_value = int(row["stock_actual"])
    committed_value = int(row["apartado_cantidad"])
    stock_minimo = row.get("stock_minimo")
    stock_minimo_int = int(stock_minimo) if stock_minimo is not None else None
    below_min = stock_minimo_int is not None and stock_value < stock_minimo_int
    stock_tone = "danger" if stock_value == 0 else "warning" if (stock_value <= 3 or below_min) else "positive"
    row_tone = _build_inventory_row_tone(
        stock_value=stock_value,
        committed_value=committed_value,
        variant_active=bool(row["variante_activa"]),
        qr_exists=bool(row["qr_exists"]),
        below_min=below_min,
    )
    status_text = "ACTIVA" if row["variante_activa"] else "INACTIVA"
    status_tone = "positive" if row["variante_activa"] else "muted"
    qr_text = "Listo" if row["qr_exists"] else "Pendiente"
    qr_tone = "positive" if row["qr_exists"] else "warning"
    conteo_text = _format_ultimo_conteo(row.get("ultimo_conteo_at"))
    return InventoryTableRowView(
        variant_id=int(row["variante_id"]),
        values=(
            row["sku"],
            row["producto_nombre_base"],
            row["talla"],
            row["color"],
            _build_stock_table_text(stock_value, stock_minimo=stock_minimo_int),
            committed_value,
            status_text,
            qr_text,
            conteo_text,
        ),
        row_tone=row_tone,
        stock_tone=stock_tone,
        committed_tone="reserved" if committed_value > 0 else None,
        status_tone=status_tone,
        qr_tone=qr_tone,
    )


def _build_stock_table_text(stock_value: int, *, stock_minimo: int | None = None) -> str:
    if stock_value == 0:
        return "0 Agotado"
    if stock_minimo is not None and stock_value < stock_minimo:
        return f"{stock_value} Bajo mín"
    if stock_value <= 3:
        return f"{stock_value} Bajo"
    return f"{stock_value} OK"


def _format_ultimo_conteo(ultimo_conteo_at: object) -> str:
    if ultimo_conteo_at is None:
        return "Nunca"
    try:
        dt = ultimo_conteo_at  # type: ignore[assignment]
        if dt.tzinfo is None:  # type: ignore[union-attr]
            dt = dt.replace(tzinfo=timezone.utc)  # type: ignore[union-attr]
        days = (datetime.now(tz=timezone.utc) - dt).days  # type: ignore[operator]
        if days == 0:
            return "Hoy"
        if days == 1:
            return "Ayer"
        return f"Hace {days}d"
    except Exception:
        return "-"


def _build_inventory_row_tone(
    *,
    stock_value: int,
    committed_value: int,
    variant_active: bool,
    qr_exists: bool,
    below_min: bool = False,
) -> str | None:
    if not variant_active:
        return "muted"
    if stock_value == 0:
        return "danger"
    if below_min:
        return "warning"
    return None
