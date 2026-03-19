"""Carga del snapshot visible para el tab de Historial."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HistorySnapshotFilters:
    source_filter: str
    entity_filter: str
    sku_filter: str
    type_filter: str
    start_datetime: object | None
    end_datetime: object | None


def load_history_snapshot_rows(
    session,
    *,
    filters: HistorySnapshotFilters,
    inventory_loader=None,
    catalog_loader=None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if filters.source_filter in {"", "inventory"}:
        rows.extend((inventory_loader or _load_inventory_history_rows)(session, filters))
    if filters.source_filter in {"", "catalog"}:
        rows.extend((catalog_loader or _load_catalog_history_rows)(session, filters))
    return rows


def _load_inventory_history_rows(session, filters: HistorySnapshotFilters) -> list[dict[str, object]]:
    select, or_, desc, movimiento_model, variante_model, producto_model, tipo_movimiento_enum = (
        _resolve_history_inventory_dependencies()
    )
    statement = (
        select(
            movimiento_model.created_at,
            variante_model.sku,
            movimiento_model.tipo_movimiento,
            movimiento_model.cantidad,
            movimiento_model.stock_posterior,
            movimiento_model.referencia,
            movimiento_model.creado_por,
            movimiento_model.observacion,
            producto_model.nombre,
        )
        .join(movimiento_model.variante)
        .join(variante_model.producto)
        .order_by(desc(movimiento_model.created_at))
        .limit(200)
    )

    if filters.sku_filter:
        statement = statement.where(
            or_(
                variante_model.sku.ilike(f"%{filters.sku_filter}%"),
                producto_model.nombre.ilike(f"%{filters.sku_filter}%"),
                movimiento_model.referencia.ilike(f"%{filters.sku_filter}%"),
                movimiento_model.creado_por.ilike(f"%{filters.sku_filter}%"),
                movimiento_model.observacion.ilike(f"%{filters.sku_filter}%"),
            )
        )
    if filters.entity_filter and filters.entity_filter != "PRESENTACION":
        statement = statement.where(variante_model.id == -1)
    if filters.type_filter.startswith("inventory:"):
        statement = statement.where(
            movimiento_model.tipo_movimiento == tipo_movimiento_enum(filters.type_filter.split(":", 1)[1])
        )
    if filters.start_datetime is not None:
        statement = statement.where(movimiento_model.created_at >= filters.start_datetime)
    if filters.end_datetime is not None:
        statement = statement.where(movimiento_model.created_at < filters.end_datetime)

    return [
        {
            "fecha": row[0],
            "origen": "Inventario",
            "registro": row[1],
            "entidad": "PRESENTACION",
            "tipo": row[2].value if row[2] else "",
            "cambio": row[3],
            "resultado": row[4],
            "usuario": row[6],
            "detalle": " | ".join(part for part in [row[8], row[5], row[7]] if part),
        }
        for row in session.execute(statement).all()
    ]


def _load_catalog_history_rows(session, filters: HistorySnapshotFilters) -> list[dict[str, object]]:
    select, or_, desc, cambio_model, usuario_model, tipo_entidad_enum, tipo_cambio_enum = (
        _resolve_history_catalog_dependencies()
    )
    statement = (
        select(
            cambio_model.created_at,
            cambio_model.descripcion_entidad,
            cambio_model.accion,
            cambio_model.campo,
            cambio_model.valor_anterior,
            cambio_model.valor_nuevo,
            usuario_model.username,
            cambio_model.observacion,
            cambio_model.entidad_tipo,
        )
        .join(cambio_model.usuario)
        .order_by(desc(cambio_model.created_at))
        .limit(200)
    )

    if filters.sku_filter:
        statement = statement.where(
            or_(
                cambio_model.descripcion_entidad.ilike(f"%{filters.sku_filter}%"),
                cambio_model.campo.ilike(f"%{filters.sku_filter}%"),
                cambio_model.valor_anterior.ilike(f"%{filters.sku_filter}%"),
                cambio_model.valor_nuevo.ilike(f"%{filters.sku_filter}%"),
                cambio_model.observacion.ilike(f"%{filters.sku_filter}%"),
                usuario_model.username.ilike(f"%{filters.sku_filter}%"),
            )
        )
    if filters.entity_filter:
        statement = statement.where(cambio_model.entidad_tipo == tipo_entidad_enum(filters.entity_filter))
    if filters.type_filter.startswith("catalog:"):
        statement = statement.where(cambio_model.accion == tipo_cambio_enum(filters.type_filter.split(":", 1)[1]))
    if filters.start_datetime is not None:
        statement = statement.where(cambio_model.created_at >= filters.start_datetime)
    if filters.end_datetime is not None:
        statement = statement.where(cambio_model.created_at < filters.end_datetime)

    return [
        {
            "fecha": row[0],
            "origen": "Catalogo",
            "registro": row[1],
            "entidad": row[8].value if row[8] else "",
            "tipo": f"{row[2].value} · {row[3]}",
            "cambio": row[4] if row[4] is not None else "—",
            "resultado": row[5] if row[5] is not None else "—",
            "usuario": row[6],
            "detalle": row[7] or "",
        }
        for row in session.execute(statement).all()
    ]


def _resolve_history_inventory_dependencies():
    from sqlalchemy import desc, or_, select

    from pos_uniformes.database.models import (
        MovimientoInventario,
        Producto,
        TipoMovimientoInventario,
        Variante,
    )

    return select, or_, desc, MovimientoInventario, Variante, Producto, TipoMovimientoInventario


def _resolve_history_catalog_dependencies():
    from sqlalchemy import desc, or_, select

    from pos_uniformes.database.models import (
        CambioCatalogo,
        TipoCambioCatalogo,
        TipoEntidadCatalogo,
        Usuario,
    )

    return select, or_, desc, CambioCatalogo, Usuario, TipoEntidadCatalogo, TipoCambioCatalogo
