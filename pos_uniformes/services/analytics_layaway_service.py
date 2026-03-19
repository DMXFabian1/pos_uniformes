"""Carga el snapshot de apartados para Analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class AnalyticsLayawaySnapshot:
    active_count: int
    pending_balance: Decimal
    overdue_count: int
    delivered_in_period: int


def load_analytics_layaway_snapshot(
    session,
    *,
    period_start: datetime,
    period_end: datetime,
    today: date | None = None,
) -> AnalyticsLayawaySnapshot:
    snapshot_date = today or date.today()
    return AnalyticsLayawaySnapshot(
        active_count=int(_count_active_layaways(session)),
        pending_balance=Decimal(_sum_pending_balance(session)),
        overdue_count=int(_count_overdue_layaways(session, today=snapshot_date)),
        delivered_in_period=int(_count_delivered_layaways(session, period_start=period_start, period_end=period_end)),
    )


def _count_active_layaways(session) -> int:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import Apartado, EstadoApartado

    return session.scalar(
        select(func.count(Apartado.id)).where(Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]))
    ) or 0


def _sum_pending_balance(session):
    from sqlalchemy import func, select

    from pos_uniformes.database.models import Apartado, EstadoApartado

    return session.scalar(
        select(func.coalesce(func.sum(Apartado.saldo_pendiente), 0)).where(
            Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO])
        )
    ) or Decimal("0.00")


def _count_overdue_layaways(session, *, today: date) -> int:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import Apartado, EstadoApartado

    return session.scalar(
        select(func.count(Apartado.id)).where(
            Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]),
            Apartado.fecha_compromiso.is_not(None),
            func.date(Apartado.fecha_compromiso) < today,
        )
    ) or 0


def _count_delivered_layaways(session, *, period_start: datetime, period_end: datetime) -> int:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import Apartado, EstadoApartado

    return session.scalar(
        select(func.count(Apartado.id)).where(
            Apartado.estado == EstadoApartado.ENTREGADO,
            Apartado.entregado_at.is_not(None),
            Apartado.entregado_at >= period_start,
            Apartado.entregado_at < period_end,
        )
    ) or 0
