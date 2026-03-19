"""Carga metricas de alertas para Apartados."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class LayawayAlertsSnapshot:
    overdue_count: int
    due_today_count: int
    due_week_count: int


def load_layaway_alerts_snapshot(session, *, today: date | None = None) -> LayawayAlertsSnapshot:
    snapshot_date = today or date.today()
    week_limit = snapshot_date + timedelta(days=7)
    return LayawayAlertsSnapshot(
        overdue_count=int(_count_layaways_overdue(session, today=snapshot_date)),
        due_today_count=int(_count_layaways_due_today(session, today=snapshot_date)),
        due_week_count=int(_count_layaways_due_week(session, today=snapshot_date, week_limit=week_limit)),
    )


def _count_layaways_overdue(session, *, today: date) -> int:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import Apartado, EstadoApartado

    return session.scalar(
        select(func.count(Apartado.id)).where(
            Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]),
            Apartado.fecha_compromiso.is_not(None),
            func.date(Apartado.fecha_compromiso) < today,
        )
    ) or 0


def _count_layaways_due_today(session, *, today: date) -> int:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import Apartado, EstadoApartado

    return session.scalar(
        select(func.count(Apartado.id)).where(
            Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]),
            Apartado.fecha_compromiso.is_not(None),
            func.date(Apartado.fecha_compromiso) == today,
        )
    ) or 0


def _count_layaways_due_week(session, *, today: date, week_limit: date) -> int:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import Apartado, EstadoApartado

    return session.scalar(
        select(func.count(Apartado.id)).where(
            Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]),
            Apartado.fecha_compromiso.is_not(None),
            func.date(Apartado.fecha_compromiso) > today,
            func.date(Apartado.fecha_compromiso) <= week_limit,
        )
    ) or 0
