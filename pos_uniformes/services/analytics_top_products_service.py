"""Carga el snapshot base de top productos para Analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AnalyticsTopProductSnapshotRow:
    sku: object
    product_name: object
    units_sold: object
    revenue: object


def load_analytics_top_product_snapshot_rows(
    session,
    *,
    period_start: datetime,
    period_end: datetime,
    selected_client_id: object,
    limit: int = 10,
) -> tuple[AnalyticsTopProductSnapshotRow, ...]:
    raw_rows = _execute_analytics_top_products_query(
        session,
        period_start=period_start,
        period_end=period_end,
        selected_client_id=selected_client_id,
        limit=limit,
    )
    return tuple(
        AnalyticsTopProductSnapshotRow(
            sku=row[0],
            product_name=row[1],
            units_sold=row[2],
            revenue=row[3],
        )
        for row in raw_rows
    )


def _execute_analytics_top_products_query(
    session,
    *,
    period_start: datetime,
    period_end: datetime,
    selected_client_id: object,
    limit: int,
):
    from sqlalchemy import desc, func, select

    from pos_uniformes.database.models import EstadoVenta, Producto, Variante, Venta, VentaDetalle

    statement = (
        select(
            Variante.sku,
            Producto.nombre,
            func.coalesce(func.sum(VentaDetalle.cantidad), 0),
            func.coalesce(func.sum(VentaDetalle.subtotal_linea), 0),
        )
        .join(VentaDetalle.variante)
        .join(Variante.producto)
        .join(VentaDetalle.venta)
        .where(
            Venta.estado == EstadoVenta.CONFIRMADA,
            Venta.confirmada_at.is_not(None),
            Venta.confirmada_at >= period_start,
            Venta.confirmada_at < period_end,
            *((Venta.cliente_id == int(selected_client_id),) if selected_client_id not in {None, ""} else ()),
        )
        .group_by(Variante.sku, Producto.nombre)
        .order_by(desc(func.sum(VentaDetalle.cantidad)), Variante.sku.asc())
        .limit(limit)
    )
    return list(session.execute(statement).all())
