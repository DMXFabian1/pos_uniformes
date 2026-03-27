"""Servicios puros para el flujo de conteo fisico rapido."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.utils.product_name import sanitize_product_display_name


@dataclass(frozen=True)
class InventoryCountVariantView:
    variante_id: int
    sku: str
    producto_nombre: str
    talla: str
    color: str
    escuela_nombre: str
    stock_actual: int


@dataclass(frozen=True)
class InventoryCountRow:
    variante_id: int
    sku: str
    producto_nombre: str
    stock_sistema: int
    stock_contado: int
    delta: int


@dataclass(frozen=True)
class InventoryCountSummary:
    changed_rows: int
    increases: int
    decreases: int
    zero_rows: int


def load_inventory_count_variant_by_sku(session, sku: str) -> InventoryCountVariantView | None:
    from sqlalchemy import func, select
    from sqlalchemy.orm import joinedload

    from pos_uniformes.database.models import Producto, Variante

    normalized_sku = sku.strip()
    if not normalized_sku:
        return None

    variante = session.scalar(
        select(Variante)
        .options(
            joinedload(Variante.producto).joinedload(Producto.escuela),
        )
        .where(func.lower(Variante.sku) == normalized_sku.lower())
    )
    if variante is None:
        return None

    return InventoryCountVariantView(
        variante_id=int(variante.id),
        sku=str(variante.sku),
        producto_nombre=sanitize_product_display_name(variante.producto.nombre),
        talla=str(variante.talla or "-"),
        color=str(variante.color or "-"),
        escuela_nombre=str(variante.producto.escuela.nombre if variante.producto.escuela is not None else "General"),
        stock_actual=int(variante.stock_actual),
    )


def build_inventory_count_row(
    variant: InventoryCountVariantView,
    *,
    counted_stock: int,
) -> InventoryCountRow:
    stock_counted = int(counted_stock)
    stock_system = int(variant.stock_actual)
    return InventoryCountRow(
        variante_id=int(variant.variante_id),
        sku=str(variant.sku),
        producto_nombre=str(variant.producto_nombre),
        stock_sistema=stock_system,
        stock_contado=stock_counted,
        delta=stock_counted - stock_system,
    )


def upsert_inventory_count_row(
    rows: list[InventoryCountRow],
    new_row: InventoryCountRow,
) -> list[InventoryCountRow]:
    updated_rows = [row for row in rows if int(row.variante_id) != int(new_row.variante_id)]
    updated_rows.append(new_row)
    return sorted(updated_rows, key=lambda row: row.sku)


def remove_inventory_count_row(rows: list[InventoryCountRow], *, variante_id: int) -> list[InventoryCountRow]:
    return [row for row in rows if int(row.variante_id) != int(variante_id)]


def build_inventory_count_summary(rows: list[InventoryCountRow]) -> InventoryCountSummary:
    changed_rows = sum(1 for row in rows if int(row.delta) != 0)
    increases = sum(1 for row in rows if int(row.delta) > 0)
    decreases = sum(1 for row in rows if int(row.delta) < 0)
    zero_rows = sum(1 for row in rows if int(row.delta) == 0)
    return InventoryCountSummary(
        changed_rows=changed_rows,
        increases=increases,
        decreases=decreases,
        zero_rows=zero_rows,
    )


def filter_inventory_count_changed_rows(rows: list[InventoryCountRow]) -> list[InventoryCountRow]:
    return [row for row in rows if int(row.delta) != 0]


def build_inventory_count_payload(
    *,
    reference: str,
    observation: str,
    rows: list[InventoryCountRow],
) -> dict[str, object]:
    changed_rows = filter_inventory_count_changed_rows(rows)
    return {
        "reference": reference.strip(),
        "observation": observation.strip(),
        "rows": [
            {
                "variante_id": int(row.variante_id),
                "sku": str(row.sku),
                "stock_sistema": int(row.stock_sistema),
                "stock_contado": int(row.stock_contado),
                "delta": int(row.delta),
            }
            for row in changed_rows
        ],
    }
