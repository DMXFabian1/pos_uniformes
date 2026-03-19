"""Carga el snapshot base de top clientes para Analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AnalyticsTopClientSnapshotRow:
    client_name: object
    client_code: object
    sales_count: object
    amount: object


def load_analytics_top_client_snapshot_rows(
    session,
    *,
    period_start: datetime,
    period_end: datetime,
    selected_client_id: object,
    limit: int = 10,
) -> tuple[AnalyticsTopClientSnapshotRow, ...]:
    raw_rows = _execute_analytics_top_clients_query(
        session,
        period_start=period_start,
        period_end=period_end,
        selected_client_id=selected_client_id,
        limit=limit,
    )
    return tuple(
        AnalyticsTopClientSnapshotRow(
            client_name=row[0],
            client_code=row[1],
            sales_count=row[2],
            amount=row[3],
        )
        for row in raw_rows
    )


def _execute_analytics_top_clients_query(
    session,
    *,
    period_start: datetime,
    period_end: datetime,
    selected_client_id: object,
    limit: int,
):
    from sqlalchemy import desc, func, select

    from pos_uniformes.database.models import Cliente, EstadoVenta, Venta

    statement = (
        select(
            Cliente.nombre,
            Cliente.codigo_cliente,
            func.count(Venta.id),
            func.coalesce(func.sum(Venta.total), 0),
        )
        .join(Venta, Venta.cliente_id == Cliente.id)
        .where(
            Venta.estado == EstadoVenta.CONFIRMADA,
            Venta.confirmada_at.is_not(None),
            Venta.confirmada_at >= period_start,
            Venta.confirmada_at < period_end,
            *((Venta.cliente_id == int(selected_client_id),) if selected_client_id not in {None, ""} else ()),
        )
        .group_by(Cliente.id, Cliente.nombre, Cliente.codigo_cliente)
        .order_by(desc(func.sum(Venta.total)), Cliente.nombre.asc())
        .limit(limit)
    )
    return list(session.execute(statement).all())
