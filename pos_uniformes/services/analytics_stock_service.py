"""Carga el snapshot de stock critico para Analytics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyticsStockSnapshotRow:
    sku: object
    product_name: object
    stock_actual: object
    reserved_quantity: object
    is_active: object


def load_analytics_stock_snapshot_rows(
    session,
    *,
    limit: int = 10,
) -> tuple[AnalyticsStockSnapshotRow, ...]:
    raw_rows = _execute_analytics_stock_query(session, limit=limit)
    return tuple(
        AnalyticsStockSnapshotRow(
            sku=row[0],
            product_name=row[1],
            stock_actual=row[2],
            reserved_quantity=row[3],
            is_active=row[4],
        )
        for row in raw_rows
    )


def _execute_analytics_stock_query(session, *, limit: int):
    from sqlalchemy import func, or_, select

    from pos_uniformes.database.models import Apartado, ApartadoDetalle, EstadoApartado, Producto, Variante

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
            Variante.sku,
            Producto.nombre,
            Variante.stock_actual,
            func.coalesce(layaway_reserved_subquery.c.apartado_cantidad, 0),
            Variante.activo,
        )
        .join(Variante.producto)
        .outerjoin(layaway_reserved_subquery, layaway_reserved_subquery.c.variante_id == Variante.id)
        .where(or_(Variante.stock_actual <= 3, Variante.activo.is_(False)))
        .order_by(Variante.stock_actual.asc(), Producto.nombre.asc(), Variante.sku.asc())
        .limit(limit)
    )
    return list(session.execute(statement).all())
