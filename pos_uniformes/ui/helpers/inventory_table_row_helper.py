"""Filas visibles y tonos de la tabla de Inventario."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pos_uniformes.services.inventario_existencia_service import (
    AGOTADO,
    BAJO_MINIMO,
    NEGATIVO,
    clasificar_existencia,
    es_fila_virtual,
    texto_existencia,
    tono_existencia,
)


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
    # La cifra es el TOTAL (tienda + bodega + piso), igual que chips y filtros.
    stock_total = int(row["stock_actual"])
    stock_bodega = int(row.get("stock_bodega", 0))
    stock_piso = int(row.get("stock_piso", 0))
    committed_value = int(row["apartado_cantidad"])
    stock_minimo = row.get("stock_minimo")
    stock_minimo_int = int(stock_minimo) if stock_minimo is not None else None
    virtual = es_fila_virtual(row)
    clase = clasificar_existencia(stock_total, stock_minimo=stock_minimo_int, virtual=virtual)
    stock_tone = tono_existencia(stock_total, stock_minimo=stock_minimo_int, virtual=virtual)
    row_tone = _build_inventory_row_tone(
        clase=clase,
        variant_active=bool(row["variante_activa"]),
    )
    status_text = "ACTIVA" if row["variante_activa"] else "INACTIVA"
    status_tone = "positive" if row["variante_activa"] else "muted"
    qr_text = "Listo" if row["qr_exists"] else "Pendiente"
    qr_tone = "positive" if row["qr_exists"] else "warning"
    conteo_raw = row.get("ultimo_conteo_at")
    conteo_text = _format_ultimo_conteo(conteo_raw if isinstance(conteo_raw, datetime) else None)
    return InventoryTableRowView(
        variant_id=int(row["variante_id"]),
        values=(
            row["sku"],
            row["producto_nombre_base"],
            row["talla"],
            row["color"],
            texto_existencia(stock_total, stock_minimo=stock_minimo_int, virtual=virtual),
            stock_piso if stock_piso > 0 else "",
            stock_bodega if stock_bodega > 0 else "",
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


def _format_ultimo_conteo(ultimo_conteo_at: datetime | None) -> str:
    if ultimo_conteo_at is None:
        return "Nunca"
    try:
        dt = ultimo_conteo_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(tz=timezone.utc) - dt).days
        if days == 0:
            return "Hoy"
        if days == 1:
            return "Ayer"
        return f"Hace {days}d"
    except Exception:
        return "-"


def _build_inventory_row_tone(*, clase: str, variant_active: bool) -> str | None:
    if not variant_active:
        return "muted"
    if clase in (NEGATIVO, AGOTADO):
        return "danger"
    if clase == BAJO_MINIMO:
        return "warning"
    return None
