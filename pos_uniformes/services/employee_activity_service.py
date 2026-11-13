"""Resumen operativo para actividad reciente de empleadas.

2026-11-12, Daniel: «la caja antigua ya no es de utilidad, todo lo demás
corre en libreta y kioskos» → «Pantallas con datos viejos». La ficha de
Configuración › Empleadas leía la tabla `venta` de la Caja antigua (lo que la
empleada se compraba a crédito) y todas salían «Sin actividad». Ahora lee la
Libreta (`LibretaVenta.employee_code`) con el MISMO criterio que el ranking
del mismo diálogo (`ranking_libreta_service`): lo que VENDE cada empleada.

- Tickets y piezas: sus operaciones (`cuenta_como_operacion`: venta y
  apartado; ni el abono ni su propia compra con precio especial).
- Monto: el importe de sus ventas (solo tipo venta), como «Importe ventas»
  del ranking; el apartado no suma su valor aquí.
- Una operación anulada se borra de la Libreta: ya no cuenta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import func, select

from pos_uniformes.database.models import Empleada, LibretaVenta
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
    operaciones: list[object] | tuple[object, ...],
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

    from pos_uniformes.services.libreta_service import clave_operacion, cuenta_como_operacion

    last_sale_at: datetime | None = None
    #: Ventas unidas en una operación son 1 ticket (2026-11-13).
    claves_periodo: set = set()
    claves_dia: dict = {}
    for sale in operaciones:
        # El criterio del ranking: solo lo que cuenta como operación (venta y
        # apartado, sin su propia compra con precio especial).
        if not cuenta_como_operacion(sale):
            continue
        sale_datetime = getattr(sale, "created_at", None)
        if sale_datetime is None:
            continue
        sale_day = (sale_datetime.astimezone() if sale_datetime.tzinfo is not None else sale_datetime).date()
        pieces = int(getattr(sale, "piezas", 0) or 0)
        amount = (
            Decimal(str(getattr(sale, "monto_total", None) or "0")).quantize(Decimal("0.01"))
            if str(getattr(sale, "tipo", None) or "venta") == "venta"
            else Decimal("0.00")
        )
        clave = clave_operacion(sale)
        if sale_day >= summary_start:
            period_pieces += pieces
            if clave not in claves_periodo:
                claves_periodo.add(clave)
                period_tickets += 1
            period_amount = (period_amount + amount).quantize(Decimal("0.01"))
        if sale_day not in day_rows:
            continue
        current = day_rows[sale_day]
        del_dia = claves_dia.setdefault(sale_day, set())
        ticket_nuevo = clave not in del_dia
        del_dia.add(clave)
        day_rows[sale_day] = EmployeeActivityDayRow(
            day=current.day,
            day_label=current.day_label,
            pieces=current.pieces + pieces,
            tickets=current.tickets + (1 if ticket_nuevo else 0),
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
    """Versión batch de load_employee_activity_snapshot: UNA sola query a la
    Libreta para todas las empleadas. La versión por-empleada dentro de un
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
    from pos_uniformes.services.libreta_service import predicado_operacion

    sales_by_code: dict[str, list[LibretaVenta]] = {code: [] for code in codes}
    operaciones = session.scalars(
        select(LibretaVenta)
        .where(
            predicado_operacion(),
            func.upper(LibretaVenta.employee_code).in_(codes),
            LibretaVenta.created_at >= window_start,
        )
        .order_by(LibretaVenta.created_at.desc())
    ).all()
    for operacion in operaciones:
        code = str(operacion.employee_code or "").upper()
        if code in sales_by_code:
            sales_by_code[code].append(operacion)

    return {
        int(employee.id): build_employee_activity_snapshot(
            employee,
            pin_ready=EmployeeIdentityService.has_pin(employee),
            qr_ready=QrGenerator.exists_for_employee(employee),
            card_ready=EmployeeCardService.exists_for_employee(employee),
            operaciones=sales_by_code.get(str(employee.codigo).upper(), ()),
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
        operaciones=(),
        visible_name_builder=lambda _value: "",
    )
