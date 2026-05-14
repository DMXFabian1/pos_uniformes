"""Ranking de empleadas por ventas confirmadas en un periodo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from pos_uniformes.database.models import Empleada, EstadoVenta, ModoOrigenVenta, Venta


@dataclass(frozen=True)
class EmployeeRankingRow:
    rank: int
    employee_id: int | None
    employee_code: str
    display_name: str
    tickets: int
    pieces: int
    amount: Decimal
    last_sale_at: datetime | None


def load_employee_ranking(
    session,
    *,
    start_date: date,
    end_date: date,
) -> tuple[EmployeeRankingRow, ...]:
    """Ranking de empleadas por monto en [start_date, end_date] inclusive."""
    from pos_uniformes.services.employee_identity_service import EmployeeIdentityService

    window_start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    window_end = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    sales = session.scalars(
        select(Venta)
        .options(selectinload(Venta.detalles))
        .where(
            Venta.estado == EstadoVenta.CONFIRMADA,
            Venta.credit_mode == ModoOrigenVenta.EMPLOYEE,
            Venta.confirmada_at >= window_start,
            Venta.confirmada_at <= window_end,
        )
    ).all()

    aggregates: dict[str, dict] = {}
    for sale in sales:
        code = str(sale.seller_employee_code or "").strip().upper()
        if not code:
            continue
        if code not in aggregates:
            aggregates[code] = {
                "tickets": 0,
                "pieces": 0,
                "amount": Decimal("0.00"),
                "last_sale_at": None,
            }
        agg = aggregates[code]
        agg["tickets"] += 1
        agg["pieces"] += sum(int(getattr(d, "cantidad", 0) or 0) for d in sale.detalles)
        agg["amount"] = (agg["amount"] + Decimal(str(sale.total or "0"))).quantize(Decimal("0.01"))
        sale_at = sale.confirmada_at
        if sale_at is not None and (agg["last_sale_at"] is None or sale_at > agg["last_sale_at"]):
            agg["last_sale_at"] = sale_at

    employees = session.scalars(select(Empleada)).all()
    employee_by_code: dict[str, Empleada] = {
        str(emp.codigo or "").strip().upper(): emp
        for emp in employees
        if str(emp.codigo or "").strip()
    }

    sorted_codes = sorted(
        aggregates.keys(),
        key=lambda c: (-aggregates[c]["amount"], aggregates[c]["last_sale_at"] or datetime.min, c),
    )
    rows: list[EmployeeRankingRow] = []
    for rank, code in enumerate(sorted_codes, start=1):
        agg = aggregates[code]
        emp = employee_by_code.get(code)
        display_name = (
            EmployeeIdentityService.build_visible_employee_name(str(emp.nombre_completo))
            if emp is not None
            else code
        )
        rows.append(
            EmployeeRankingRow(
                rank=rank,
                employee_id=int(emp.id) if emp is not None else None,
                employee_code=code,
                display_name=display_name,
                tickets=int(agg["tickets"]),
                pieces=int(agg["pieces"]),
                amount=agg["amount"],
                last_sale_at=agg["last_sale_at"],
            )
        )
    return tuple(rows)


def build_ranking_period_dates(period: str, reference_date: date | None = None) -> tuple[date, date]:
    """Devuelve (start, end) para un nombre de periodo canonico."""
    today = reference_date if reference_date is not None else date.today()
    if period == "Hoy":
        return today, today
    if period == "7 dias":
        from datetime import timedelta
        return today - timedelta(days=6), today
    if period == "Este mes":
        return today.replace(day=1), today
    return today, today
