"""Resumen operativo para actividad reciente de empleadas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from pos_uniformes.database.models import Empleada, EstadoVenta, ModoOrigenVenta, Venta
from pos_uniformes.utils.date_format import local_day_window


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
    period_days: int
    period_label: str
    period_pieces: int
    period_tickets: int
    period_amount: Decimal
    today_pieces: int
    today_tickets: int
    today_amount: Decimal
    last_sale_at: datetime | None
    day_rows: tuple[EmployeeActivityDayRow, ...]


@dataclass(frozen=True)
class EmployeeActivityState:
    label: str
    tone: str


def build_employee_activity_snapshot(
    employee,
    *,
    pin_ready: bool,
    qr_ready: bool,
    card_ready: bool,
    sales: list[object] | tuple[object, ...],
    reference_date: date | None = None,
    history_days: int = 7,
    summary_days: int = 1,
    visible_name_builder=None,
) -> EmployeeActivitySnapshot:
    if reference_date is None:
        reference_date = date.today()
    history_days = max(int(history_days or 7), 1)
    summary_days = max(int(summary_days or 1), 1)
    if visible_name_builder is None:
        from pos_uniformes.services.employee_identity_service import EmployeeIdentityService

        visible_name_builder = EmployeeIdentityService.build_visible_employee_name

    day_rows: dict[date, EmployeeActivityDayRow] = {}
    target_days = [reference_date - timedelta(days=offset) for offset in range(history_days)]
    summary_start = reference_date - timedelta(days=summary_days - 1)
    period_pieces = 0
    period_tickets = 0
    period_amount = Decimal("0.00")
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
        sale_day = (sale_datetime.astimezone() if sale_datetime.tzinfo is not None else sale_datetime).date()
        pieces = sum(int(getattr(detail, "cantidad", 0) or 0) for detail in getattr(sale, "detalles", ()))
        amount = Decimal(str(getattr(sale, "total", Decimal("0.00")) or Decimal("0.00"))).quantize(Decimal("0.01"))
        if sale_day >= summary_start:
            period_pieces += pieces
            period_tickets += 1
            period_amount = (period_amount + amount).quantize(Decimal("0.01"))
        if sale_day not in day_rows:
            continue
        current = day_rows[sale_day]
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
        period_days=summary_days,
        period_label="Hoy" if summary_days == 1 else f"{summary_days} dias",
        period_pieces=period_pieces,
        period_tickets=period_tickets,
        period_amount=period_amount,
        today_pieces=today_row.pieces,
        today_tickets=today_row.tickets,
        today_amount=today_row.amount,
        last_sale_at=last_sale_at,
        day_rows=ordered_rows,
    )


def build_employee_activity_state(snapshot: EmployeeActivitySnapshot) -> EmployeeActivityState:
    today_pieces = int(getattr(snapshot, "today_pieces", 0) or 0)
    today_tickets = int(getattr(snapshot, "today_tickets", 0) or 0)
    day_rows = tuple(getattr(snapshot, "day_rows", ()) or ())
    if today_pieces > 0 or today_tickets > 0:
        return EmployeeActivityState(label="Activa hoy", tone="positive")
    if any(
        int(getattr(day_row, "pieces", 0) or 0) > 0 or int(getattr(day_row, "tickets", 0) or 0) > 0
        for day_row in day_rows[1:]
    ):
        return EmployeeActivityState(label="Activa 7d", tone="warning")
    return EmployeeActivityState(label="Sin actividad", tone="muted")


def build_employee_activity_sort_key(snapshot: EmployeeActivitySnapshot) -> tuple[int, int, float, str]:
    state = build_employee_activity_state(snapshot)
    state_priority = {
        "Activa hoy": 0,
        "Activa 7d": 1,
        "Sin actividad": 2,
    }.get(state.label, 3)
    last_sale_at = getattr(snapshot, "last_sale_at", None)
    last_sale_timestamp = last_sale_at.timestamp() if last_sale_at is not None else 0.0
    display_name = (
        str(getattr(snapshot, "visible_name", "") or getattr(snapshot, "full_name", "") or "").strip().lower()
    )
    return (
        state_priority,
        -int(getattr(snapshot, "today_pieces", 0) or 0),
        -last_sale_timestamp,
        display_name,
    )


def load_employee_activity_snapshot(
    session,
    *,
    employee_id: int,
    reference_date: date | None = None,
    history_days: int = 7,
    summary_days: int = 1,
) -> EmployeeActivitySnapshot:
    """Snapshot de UNA empleada. Delegado a la versión batch para que la
    ventana de fechas y los filtros de venta vivan en un solo lugar."""
    employee = session.get(Empleada, employee_id)
    if employee is None:
        raise ValueError("No se encontro la empleada seleccionada.")
    return load_employee_activity_snapshots(
        session,
        [employee],
        reference_date=reference_date,
        history_days=history_days,
        summary_days=summary_days,
    )[int(employee.id)]


def load_employee_activity_snapshots(
    session,
    employees,
    *,
    reference_date: date | None = None,
    history_days: int = 7,
    summary_days: int = 1,
) -> dict[int, EmployeeActivitySnapshot]:
    """Versión batch de load_employee_activity_snapshot: UNA sola query de
    ventas para todas las empleadas. La versión por-empleada dentro de un
    loop era un N+1 que congelaba la pestaña de Configuración."""
    from pos_uniformes.services.employee_card_service import EmployeeCardService
    from pos_uniformes.services.employee_identity_service import EmployeeIdentityService
    from pos_uniformes.utils.qr_generator import QrGenerator

    employees = list(employees)
    if not employees:
        return {}

    if reference_date is None:
        reference_date = date.today()
    history_days = max(int(history_days or 7), 1)
    summary_days = max(int(summary_days or 1), 1)
    lookback_days = max(history_days, summary_days)
    window_start, _ = local_day_window(reference_date - timedelta(days=lookback_days - 1))

    codes = {str(employee.codigo).upper() for employee in employees}
    sales_by_code: dict[str, list[Venta]] = {code: [] for code in codes}
    ventas = session.scalars(
        select(Venta)
        .options(selectinload(Venta.detalles))
        .where(
            Venta.estado == EstadoVenta.CONFIRMADA,
            Venta.credit_mode == ModoOrigenVenta.EMPLOYEE,
            func.upper(Venta.seller_employee_code).in_(codes),
            Venta.confirmada_at >= window_start,
        )
        .order_by(Venta.confirmada_at.desc())
    ).all()
    for venta in ventas:
        code = str(venta.seller_employee_code or "").upper()
        if code in sales_by_code:
            sales_by_code[code].append(venta)

    return {
        int(employee.id): build_employee_activity_snapshot(
            employee,
            pin_ready=EmployeeIdentityService.has_pin(employee),
            qr_ready=QrGenerator.exists_for_employee(employee),
            card_ready=EmployeeCardService.exists_for_employee(employee),
            sales=sales_by_code.get(str(employee.codigo).upper(), ()),
            reference_date=reference_date,
            history_days=history_days,
            summary_days=summary_days,
            visible_name_builder=EmployeeIdentityService.build_visible_employee_name,
        )
        for employee in employees
    }


def build_employee_activity_empty_snapshot() -> EmployeeActivitySnapshot:
    return build_employee_activity_snapshot(
        SimpleNamespace(id=0, codigo="", nombre_completo="", activo=False),
        pin_ready=False,
        qr_ready=False,
        card_ready=False,
        sales=(),
        visible_name_builder=lambda _value: "",
    )
