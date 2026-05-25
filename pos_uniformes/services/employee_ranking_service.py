"""Ranking de empleadas por ventas confirmadas y apartados en un periodo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from pos_uniformes.database.models import (
    Apartado,
    ApartadoAbono,
    ApartadoDetalle,
    Empleada,
    EstadoApartado,
    EstadoVenta,
    ModoOrigenVenta,
    Venta,
)
from pos_uniformes.utils.date_format import local_day_window


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

    window_start, _ = local_day_window(start_date)
    _, window_end = local_day_window(end_date)

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

    def _ensure_agg(code: str) -> dict:
        if code not in aggregates:
            aggregates[code] = {
                "tickets": 0,
                "pieces": 0,
                "amount": Decimal("0.00"),
                "last_sale_at": None,
            }
        return aggregates[code]

    def _update_last(agg: dict, ts: datetime | None) -> None:
        if ts is not None and (agg["last_sale_at"] is None or ts > agg["last_sale_at"]):
            agg["last_sale_at"] = ts

    aggregates: dict[str, dict] = {}

    # --- Ventas directas con atribucion de empleada ---
    for sale in sales:
        code = str(sale.seller_employee_code or "").strip().upper()
        if not code:
            continue
        agg = _ensure_agg(code)
        agg["tickets"] += 1
        agg["pieces"] += sum(int(getattr(d, "cantidad", 0) or 0) for d in sale.detalles)
        agg["amount"] = (agg["amount"] + Decimal(str(sale.total or "0"))).quantize(Decimal("0.01"))
        _update_last(agg, sale.confirmada_at)

    # --- Apartados creados en el periodo con atribucion de empleada ---
    apartados = session.scalars(
        select(Apartado)
        .options(selectinload(Apartado.detalles), selectinload(Apartado.abonos))
        .where(
            Apartado.seller_employee_code.isnot(None),
            Apartado.estado != EstadoApartado.CANCELADO,
            Apartado.created_at >= window_start,
            Apartado.created_at <= window_end,
        )
    ).all()
    for apartado in apartados:
        code = str(apartado.seller_employee_code or "").strip().upper()
        if not code:
            continue
        anticipo = next(
            (Decimal(str(ab.monto or "0")) for ab in apartado.abonos if str(ab.referencia or "") == "ANTICIPO" and not getattr(ab, "anulado", False)),
            Decimal("0.00"),
        )
        agg = _ensure_agg(code)
        agg["tickets"] += 1
        agg["pieces"] += sum(int(getattr(d, "cantidad", 0) or 0) for d in apartado.detalles)
        agg["amount"] = (agg["amount"] + anticipo).quantize(Decimal("0.01"))
        _update_last(agg, apartado.created_at)

    # --- Abonos adicionales (excluye ANTICIPO, ya contado en la creacion) ---
    additional_abonos = session.scalars(
        select(ApartadoAbono)
        .where(
            ApartadoAbono.seller_employee_code.isnot(None),
            ApartadoAbono.referencia != "ANTICIPO",
            ApartadoAbono.created_at >= window_start,
            ApartadoAbono.created_at <= window_end,
        )
    ).all()
    for abono in additional_abonos:
        code = str(abono.seller_employee_code or "").strip().upper()
        if not code:
            continue
        agg = _ensure_agg(code)
        agg["amount"] = (agg["amount"] + Decimal(str(abono.monto or "0"))).quantize(Decimal("0.01"))
        _update_last(agg, abono.created_at)

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
