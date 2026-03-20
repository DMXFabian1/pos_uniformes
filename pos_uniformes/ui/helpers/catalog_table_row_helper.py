"""Filas visibles y tonos de la tabla de Catalogo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogTableRowView:
    variant_id: int
    values: tuple[object, ...]
    row_tone: str | None
    stock_tone: str
    layaway_tone: str | None
    status_tone: str


def build_catalog_table_row_views(visible_rows: list[dict[str, object]]) -> tuple[CatalogTableRowView, ...]:
    return tuple(build_catalog_table_row_view(row) for row in visible_rows)


def build_catalog_table_row_view(row: dict[str, object]) -> CatalogTableRowView:
    stock_value = int(row["stock_actual"])
    committed_value = int(row["apartado_cantidad"])
    is_active = bool(row["variante_activo"])
    stock_tone = "danger" if stock_value == 0 else "warning" if stock_value <= 3 else "positive"
    return CatalogTableRowView(
        variant_id=int(row["variante_id"]),
        values=(
            row["sku"],
            row["escuela_nombre"],
            row["tipo_prenda_nombre"],
            row["tipo_pieza_nombre"],
            row["marca_nombre"],
            row["producto_nombre_base"],
            row["talla"],
            row["color"],
            row["precio_venta"],
            stock_value,
            committed_value,
            row["variante_estado"],
        ),
        row_tone=_build_catalog_row_tone(
            stock_value=stock_value,
            committed_value=committed_value,
            is_active=is_active,
        ),
        stock_tone=stock_tone,
        layaway_tone="warning" if committed_value > 0 else None,
        status_tone="positive" if is_active else "muted",
    )


def _build_catalog_row_tone(*, stock_value: int, committed_value: int, is_active: bool) -> str | None:
    if not is_active:
        return "muted"
    if stock_value == 0:
        return "danger"
    if stock_value <= 3:
        return "warning"
    if committed_value > 0:
        return "reserved"
    return None
