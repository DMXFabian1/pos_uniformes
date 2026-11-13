"""Carga el snapshot visible de la ficha rapida de Inventario."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.utils.date_format import format_display_datetime
from pos_uniformes.utils.product_name import sanitize_product_display_name


@dataclass(frozen=True)
class InventoryOverviewSnapshot:
    sku: str
    product_name: str
    product_active: bool
    variant_active: bool
    stock_actual: int
    apartado_cantidad: int
    talla: str
    color: str
    precio_venta: Decimal | str | int | float
    origen_etiqueta: str
    escuela_nombre: str
    tipo_prenda_nombre: str
    tipo_pieza_nombre: str
    stock_minimo: int | None
    movement_type: str | None
    movement_quantity: int | None
    movement_date: str
    # Tiene receta (conjunto armado de piezas). Sale de la propia variante, no
    # de las filas de Catálogo, para que la ficha clasifique igual que la tabla.
    es_conjunto: bool = False


def load_inventory_overview_snapshot(
    session,
    *,
    variant_id: int,
    catalog_rows: list[dict[str, object]],
) -> InventoryOverviewSnapshot:
    variante_model, movement_query, conjunto_query = _resolve_inventory_overview_models_and_query()

    variante = session.get(variante_model, int(variant_id))
    if variante is None:
        raise ValueError("Presentacion no encontrada.")

    movement = session.scalar(movement_query(variante.id))
    producto = getattr(variante, "producto", None)
    producto_id = getattr(variante, "producto_id", None) or getattr(producto, "id", None)
    es_conjunto = (
        producto_id is not None and session.scalar(conjunto_query(int(producto_id))) is True
    )
    tipo_pieza = getattr(producto, "tipo_pieza", None)
    tipo_pieza_propio = str(getattr(tipo_pieza, "nombre", "") or "").strip() or "-"
    matching_row = next(
        (row for row in catalog_rows if int(row["variante_id"]) == int(variant_id)),
        None,
    )
    movement_date = format_display_datetime(movement.created_at) if movement and movement.created_at else ""
    movement_type = movement.tipo_movimiento.value.replace("_", " ").title() if movement else None

    return InventoryOverviewSnapshot(
        sku=str(variante.sku),
        product_name=(
            str(matching_row["producto_nombre_base"])
            if matching_row is not None
            else sanitize_product_display_name(variante.producto.nombre)
        ),
        product_active=bool(matching_row["producto_activo"]) if matching_row is not None else True,
        variant_active=bool(matching_row["variante_activo"]) if matching_row is not None else bool(variante.activo),
        stock_actual=int(variante.stock_actual),
        stock_minimo=int(variante.stock_minimo) if variante.stock_minimo is not None else None,
        apartado_cantidad=int(matching_row["apartado_cantidad"]) if matching_row is not None else 0,
        talla=str(variante.talla),
        color=str(variante.color),
        precio_venta=variante.precio_venta,
        origen_etiqueta=str(matching_row["origen_etiqueta"]) if matching_row is not None else "NUEVO",
        escuela_nombre=str(matching_row["escuela_nombre"]) if matching_row is not None else "General",
        tipo_prenda_nombre=str(matching_row["tipo_prenda_nombre"]) if matching_row is not None else "-",
        tipo_pieza_nombre=(
            str(matching_row["tipo_pieza_nombre"]) if matching_row is not None else tipo_pieza_propio
        ),
        movement_type=movement_type,
        movement_quantity=int(movement.cantidad) if movement is not None else None,
        movement_date=movement_date,
        es_conjunto=bool(es_conjunto),
    )


def _resolve_inventory_overview_models_and_query():
    try:
        from sqlalchemy import desc, select

        from sqlalchemy import exists

        from pos_uniformes.database.models import ConjuntoComponente, MovimientoInventario, Variante
    except ModuleNotFoundError:
        return None, lambda _variant_db_id: None, lambda _producto_id: None

    return (
        Variante,
        lambda variant_db_id: (
            select(MovimientoInventario)
            .where(MovimientoInventario.variante_id == variant_db_id)
            .order_by(desc(MovimientoInventario.created_at))
            .limit(1)
        ),
        # Mismo criterio que conjunto_service.filtro_sin_conjuntos: tiene receta.
        lambda producto_id: select(exists().where(ConjuntoComponente.conjunto_id == producto_id)),
    )
