"""Resumen operativo para actividad reciente de empleadas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from pos_uniformes.database.models import Empleada, EstadoVenta, ModoOrigenVenta, Venta


@dataclass(frozen=True)
class EmployeeActivityDayRow:
    day: date
    day_label: str
    pieces: int
    tickets: int
    amount: Decimal


@dataclass(frozen=True)
class EmployeeActivitySnapshot:
    employee_id: int
    employee_code: str
    full_name: str
    visible_name: str
    active_label: str
    pin_label: str
    qr_label: str
    card_label: str
    today_pieces: int
    today_tickets: int
    today_amount: Decimal
    last_sale_at: datetime | None
    day_rows: tuple[EmployeeActivityDayRow, ...]


def build_employee_activity_snapshot(
    employee,
    *,
    pin_ready: bool,
    qr_ready: bool,
    card_ready: bool,
    sales: list[object] | tuple[object, ...],
    reference_date: date | None = None,
    visible_name_builder=None,
) -> EmployeeActivitySnapshot:
    if reference_date is None:
        reference_date = date.today()
    if visible_name_builder is None:
        from pos_uniformes.services.employee_identity_service import EmployeeIdentityService

        visible_name_builder = EmployeeIdentityService.build_visible_employee_name

    day_rows: dict[date, EmployeeActivityDayRow] = {}
    target_days = [reference_date - timedelta(days=offset) for offset in range(7)]
    for current_day in target_days:
        day_rows[current_day] = EmployeeActivityDayRow(
            day=current_day,
            day_label=current_day.strftime("%d/%m/%Y"),
            pieces=0,
            tickets=0,
            amount=Decimal("0.00"),
        )

    last_sale_at: datetime | None = None
    for sale in sales:
        sale_datetime = getattr(sale, "confirmada_at", None) or getattr(sale, "created_at", None)
        if sale_datetime is None:
            continue
        sale_day = sale_datetime.date()
        if sale_day not in day_rows:
            continue
        current = day_rows[sale_day]
        pieces = sum(int(getattr(detail, "cantidad", 0) or 0) for detail in getattr(sale, "detalles", ()))
        amount = Decimal(str(getattr(sale, "total", Decimal("0.00")) or Decimal("0.00"))).quantize(Decimal("0.01"))
        day_rows[sale_day] = EmployeeActivityDayRow(
            day=current.day,
            day_label=current.day_label,
            pieces=current.pieces + pieces,
            tickets=current.tickets + 1,
            amount=(current.amount + amount).quantize(Decimal("0.01")),
        )
        if last_sale_at is None or sale_datetime > last_sale_at:
            last_sale_at = sale_datetime

    ordered_rows = tuple(day_rows[current_day] for current_day in target_days)
    today_row = day_rows[reference_date]
    return EmployeeActivitySnapshot(
        employee_id=int(employee.id),
        employee_code=str(employee.codigo),
        full_name=str(employee.nombre_completo),
        visible_name=str(visible_name_builder(str(employee.nombre_completo))),
        active_label="ACTIVA" if bool(getattr(employee, "activo", False)) else "INACTIVA",
        pin_label="Listo" if pin_ready else "Pendiente",
        qr_label="Listo" if qr_ready else "Pendiente",
        card_label="Lista" if card_ready else "Pendiente",
        today_pieces=today_row.pieces,
        today_tickets=today_row.tickets,
        today_amount=today_row.amount,
        last_sale_at=last_sale_at,
        day_rows=ordered_rows,
    )


def load_employee_activity_snapshot(session, *, employee_id: int, reference_date: date | None = None) -> EmployeeActivitySnapshot:
    from pos_uniformes.services.employee_card_service import EmployeeCardService
    from pos_uniformes.services.employee_identity_service import EmployeeIdentityService
    from pos_uniformes.utils.qr_generator import QrGenerator

    employee = session.get(Empleada, employee_id)
    if employee is None:
        raise ValueError("No se encontro la empleada seleccionada.")

    if reference_date is None:
        reference_date = date.today()
    window_start = datetime.combine(reference_date - timedelta(days=6), datetime.min.time())
    sales = (
        session.scalars(
            select(Venta)
            .options(selectinload(Venta.detalles))
            .where(
                Venta.estado == EstadoVenta.CONFIRMADA,
                Venta.credit_mode == ModoOrigenVenta.EMPLOYEE,
                func.upper(Venta.seller_employee_code) == str(employee.codigo).upper(),
                Venta.confirmada_at >= window_start,
            )
            .order_by(Venta.confirmada_at.desc())
        ).all()
    )
    return build_employee_activity_snapshot(
        employee,
        pin_ready=EmployeeIdentityService.has_pin(employee),
        qr_ready=QrGenerator.exists_for_employee(employee),
        card_ready=EmployeeCardService.exists_for_employee(employee),
        sales=sales,
        reference_date=reference_date,
        visible_name_builder=EmployeeIdentityService.build_visible_employee_name,
    )


def build_employee_activity_empty_snapshot() -> EmployeeActivitySnapshot:
    return build_employee_activity_snapshot(
        SimpleNamespace(id=0, codigo="", nombre_completo="", activo=False),
        pin_ready=False,
        qr_ready=False,
        card_ready=False,
        sales=(),
        visible_name_builder=lambda _value: "",
    )
