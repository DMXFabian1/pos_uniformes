"""Carga el snapshot base del listado de Inventario."""

from __future__ import annotations

from decimal import Decimal

from pos_uniformes.services.search_filter_service import (
    INVENTORY_SEARCH_ALIAS_MAP,
    INVENTORY_SEARCH_GENERAL_FIELDS,
    attach_row_search_cache,
)

_inventory_qr_exists_cache: dict[str, bool] = {}

from pos_uniformes.utils.product_name import sanitize_product_display_name


def load_inventory_snapshot_rows(session) -> list[dict[str, object]]:
    return [
        _build_inventory_snapshot_row(raw_row)
        for raw_row in _execute_inventory_snapshot_query(session)
    ]


def _build_inventory_snapshot_row(row: tuple[object, ...]) -> dict[str, object]:
    qr_exists = _inventory_qr_exists(str(row[1]))
    return attach_row_search_cache(
        {
            "variante_id": row[0],
            "sku": row[1],
            "categoria_nombre": row[2],
            "marca_nombre": row[3],
            "producto_nombre": sanitize_product_display_name(row[4]),
            "producto_nombre_base": row[5],
            "escuela_nombre": row[6] or "General",
            "tipo_prenda_nombre": row[7] or "-",
            "tipo_pieza_nombre": row[8] or "-",
            "nombre_legacy": row[9],
            "origen_legacy": bool(row[10]),
            "talla": row[11],
            "color": row[12],
            "precio_venta": Decimal(row[13]).quantize(Decimal("0.01")),
            "costo_referencia": Decimal(row[14]).quantize(Decimal("0.01")) if row[14] is not None else None,
            "stock_actual": int(row[15]),
            "apartado_cantidad": int(row[16]),
            "variante_activa": bool(row[17]),
            "fallback_importacion": bool(row[18]),
            "qr_exists": qr_exists,
            "origen_etiqueta": "LEGACY" if row[10] else "NUEVO",
            "variante_estado": "ACTIVA" if row[17] else "INACTIVA",
            "fallback_text": "fallback" if bool(row[18]) else "",
        },
        alias_map=INVENTORY_SEARCH_ALIAS_MAP,
        general_fields=INVENTORY_SEARCH_GENERAL_FIELDS,
    )


def _inventory_qr_exists(sku: str) -> bool:
    cached_value = _inventory_qr_exists_cache.get(sku)
    if cached_value is not None:
        return cached_value

    from pos_uniformes.utils.qr_generator import QrGenerator

    exists = (QrGenerator.output_dir() / f"{sku}.png").exists()
    _inventory_qr_exists_cache[sku] = exists
    return exists


def invalidate_inventory_qr_exists_cache(*, sku: str | None = None) -> None:
    if sku is None:
        _inventory_qr_exists_cache.clear()
        return
    _inventory_qr_exists_cache.pop(sku, None)


def _execute_inventory_snapshot_query(session) -> list[tuple[object, ...]]:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import (
        Apartado,
        ApartadoDetalle,
        Categoria,
        Escuela,
        EstadoApartado,
        ImportacionCatalogoFila,
        Marca,
        Producto,
        TipoPieza,
        TipoPrenda,
        Variante,
    )

    layaway_reserved_subquery = (
        select(
            ApartadoDetalle.variante_id.label("variante_id"),
            func.coalesce(func.sum(ApartadoDetalle.cantidad), 0).label("apartado_cantidad"),
        )
        .join(ApartadoDetalle.apartado)
        .where(Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]))
        .group_by(ApartadoDetalle.variante_id)
        .subquery()
    )

    statement = (
        select(
            Variante.id,
            Variante.sku,
            Categoria.nombre,
            Marca.nombre,
            Producto.nombre,
            Producto.nombre_base,
            Escuela.nombre,
            TipoPrenda.nombre,
            TipoPieza.nombre,
            Variante.nombre_legacy,
            Variante.origen_legacy,
            Variante.talla,
            Variante.color,
            Variante.precio_venta,
            Variante.costo_referencia,
            Variante.stock_actual,
            func.coalesce(layaway_reserved_subquery.c.apartado_cantidad, 0),
            Variante.activo,
            func.coalesce(ImportacionCatalogoFila.producto_fallback, False),
        )
        .join(Variante.producto)
        .join(Producto.categoria)
        .join(Producto.marca)
        .outerjoin(Producto.escuela)
        .outerjoin(Producto.tipo_prenda)
        .outerjoin(Producto.tipo_pieza)
        .outerjoin(ImportacionCatalogoFila, ImportacionCatalogoFila.variante_id == Variante.id)
        .outerjoin(layaway_reserved_subquery, layaway_reserved_subquery.c.variante_id == Variante.id)
    )
    return list(session.execute(statement.order_by(Producto.nombre.asc(), Variante.sku.asc())).all())
