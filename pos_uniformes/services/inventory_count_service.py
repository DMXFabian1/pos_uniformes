"""Servicios puros para el flujo de conteo fisico rapido."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

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
    counted_pieces: int
    system_pieces: int


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


def build_inventory_count_variant_view_from_snapshot_row(
    row: Mapping[str, object],
) -> InventoryCountVariantView:
    return InventoryCountVariantView(
        variante_id=int(row["variante_id"]),
        sku=str(row["sku"]),
        producto_nombre=str(row.get("producto_nombre_base") or row.get("producto_nombre") or "-"),
        talla=str(row.get("talla") or "-"),
        color=str(row.get("color") or "-"),
        escuela_nombre=str(row.get("escuela_nombre") or "General"),
        stock_actual=int(row.get("stock_actual") or 0),
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


def build_inventory_count_rows_from_snapshot_rows(
    rows: list[Mapping[str, object]],
    *,
    use_system_count_as_counted: bool = True,
) -> list[InventoryCountRow]:
    batch_rows: list[InventoryCountRow] = []
    for row in rows:
        variant = build_inventory_count_variant_view_from_snapshot_row(row)
        batch_rows = upsert_inventory_count_row(
            batch_rows,
            build_inventory_count_row(
                variant,
                counted_stock=int(variant.stock_actual) if use_system_count_as_counted else 0,
            ),
        )
    return batch_rows


def accumulate_inventory_count_scan(
    rows: list[InventoryCountRow],
    *,
    variant: InventoryCountVariantView,
    step: int = 1,
) -> list[InventoryCountRow]:
    normalized_step = max(1, int(step))
    existing_row = next((row for row in rows if int(row.variante_id) == int(variant.variante_id)), None)
    if existing_row is None:
        return upsert_inventory_count_row(
            rows,
            build_inventory_count_row(variant, counted_stock=normalized_step),
        )
    return update_inventory_count_row_counted_stock(
        rows,
        variante_id=int(variant.variante_id),
        counted_stock=int(existing_row.stock_contado) + normalized_step,
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


def update_inventory_count_row_counted_stock(
    rows: list[InventoryCountRow],
    *,
    variante_id: int,
    counted_stock: int,
) -> list[InventoryCountRow]:
    updated_rows: list[InventoryCountRow] = []
    for row in rows:
        if int(row.variante_id) != int(variante_id):
            updated_rows.append(row)
            continue
        stock_contado = int(counted_stock)
        updated_rows.append(
            replace(
                row,
                stock_contado=stock_contado,
                delta=stock_contado - int(row.stock_sistema),
            )
        )
    return updated_rows


def build_inventory_count_summary(rows: list[InventoryCountRow]) -> InventoryCountSummary:
    changed_rows = sum(1 for row in rows if int(row.delta) != 0)
    increases = sum(1 for row in rows if int(row.delta) > 0)
    decreases = sum(1 for row in rows if int(row.delta) < 0)
    zero_rows = sum(1 for row in rows if int(row.delta) == 0)
    counted_pieces = sum(int(row.stock_contado) for row in rows)
    system_pieces = sum(int(row.stock_sistema) for row in rows)
    return InventoryCountSummary(
        changed_rows=changed_rows,
        increases=increases,
        decreases=decreases,
        zero_rows=zero_rows,
        counted_pieces=counted_pieces,
        system_pieces=system_pieces,
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
