"""Carga y resume el snapshot principal de Analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class AnalyticsSalesSnapshot:
    total_sales: Decimal
    total_tickets: int
    total_units: int
    average_ticket: Decimal
    identified_sales_count: int
    identified_income: Decimal
    repeat_clients: int
    average_per_client: Decimal


def load_confirmed_sales_for_analytics(
    session,
    *,
    period_start: datetime,
    period_end: datetime,
    selected_client_id: object,
):
    statement = _build_confirmed_sales_statement(
        period_start=period_start,
        period_end=period_end,
        selected_client_id=selected_client_id,
    )
    return list(session.scalars(statement))


def build_analytics_sales_snapshot(sales: list[object]) -> AnalyticsSalesSnapshot:
    total_sales = sum((Decimal(sale.total) for sale in sales), Decimal("0.00"))
    total_tickets = len(sales)
    total_units = sum((sum(int(detalle.cantidad) for detalle in sale.detalles) for sale in sales), 0)
    average_ticket = (
        (total_sales / Decimal(total_tickets)).quantize(Decimal("0.01"))
        if total_tickets
        else Decimal("0.00")
    )
    identified_sales = [sale for sale in sales if sale.cliente_id is not None]
    identified_income = sum((Decimal(sale.total) for sale in identified_sales), Decimal("0.00"))
    unique_clients = {int(sale.cliente_id) for sale in identified_sales if sale.cliente_id is not None}
    counts_by_client: dict[int, int] = {}
    for sale in identified_sales:
        if sale.cliente_id is None:
            continue
        client_id = int(sale.cliente_id)
        counts_by_client[client_id] = counts_by_client.get(client_id, 0) + 1
    repeat_clients = sum(1 for count in counts_by_client.values() if count > 1)
    average_per_client = (
        (identified_income / Decimal(len(unique_clients))).quantize(Decimal("0.01"))
        if unique_clients
        else Decimal("0.00")
    )
    return AnalyticsSalesSnapshot(
        total_sales=total_sales,
        total_tickets=total_tickets,
        total_units=total_units,
        average_ticket=average_ticket,
        identified_sales_count=len(identified_sales),
        identified_income=identified_income,
        repeat_clients=repeat_clients,
        average_per_client=average_per_client,
    )


def _build_confirmed_sales_statement(
    *,
    period_start: datetime,
    period_end: datetime,
    selected_client_id: object,
):
    from sqlalchemy import select

    from pos_uniformes.database.models import EstadoVenta, Venta

    statement = select(Venta).where(
        Venta.estado == EstadoVenta.CONFIRMADA,
        Venta.confirmada_at.is_not(None),
        Venta.confirmada_at >= period_start,
        Venta.confirmada_at < period_end,
    )
    if selected_client_id not in {None, ""}:
        statement = statement.where(Venta.cliente_id == int(selected_client_id))
    return statement
