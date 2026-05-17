"""Historial puntual de tickets por empleada, dia y detalle de ticket."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from pos_uniformes.database.models import EstadoVenta, ModoOrigenVenta, Variante, Venta, VentaDetalle
from pos_uniformes.utils.date_format import local_day_window


@dataclass(frozen=True)
class EmployeeDaySaleRow:
    sale_id: int
    values: tuple[object, object, object, object, object]


@dataclass(frozen=True)
class EmployeeSaleDetailLineRow:
    values: tuple[object, object, object, object, object]


@dataclass(frozen=True)
class EmployeeSaleDetailSnapshot:
    sale_id: int
    folio: str
    time_label: str
    client_name: str
    pieces: int
    total: Decimal
    rows: tuple[EmployeeSaleDetailLineRow, ...]


def build_employee_day_sale_rows(sales: list[object] | tuple[object, ...]) -> tuple[EmployeeDaySaleRow, ...]:
    rows: list[EmployeeDaySaleRow] = []
    for sale in sales:
        sale_datetime = getattr(sale, "confirmada_at", None) or getattr(sale, "created_at", None)
        if sale_datetime is not None and sale_datetime.tzinfo is not None:
            sale_datetime = sale_datetime.astimezone()
        time_label = sale_datetime.strftime("%H:%M") if sale_datetime is not None else "--:--"
        pieces = sum(int(getattr(detail, "cantidad", 0) or 0) for detail in getattr(sale, "detalles", ()))
        client = getattr(sale, "cliente", None)
        client_name = getattr(client, "nombre", None) or "Mostrador"
        total = Decimal(str(getattr(sale, "total", Decimal("0.00")) or Decimal("0.00"))).quantize(Decimal("0.01"))
        rows.append(
            EmployeeDaySaleRow(
                sale_id=int(getattr(sale, "id")),
                values=(
                    time_label,
                    getattr(sale, "folio", ""),
                    client_name,
                    pieces,
                    total,
                ),
            )
        )
    return tuple(rows)


def list_employee_day_sale_rows(session, *, employee_code: str, target_day: date) -> tuple[EmployeeDaySaleRow, ...]:
    day_start, day_end = local_day_window(target_day)
    sales = (
        session.scalars(
            select(Venta)
            .options(
                selectinload(Venta.cliente),
                selectinload(Venta.detalles),
            )
            .where(
                Venta.estado == EstadoVenta.CONFIRMADA,
                Venta.credit_mode == ModoOrigenVenta.EMPLOYEE,
                func.upper(Venta.seller_employee_code) == str(employee_code).upper(),
                Venta.confirmada_at >= day_start,
                Venta.confirmada_at < day_end,
            )
            .order_by(Venta.confirmada_at.asc(), Venta.id.asc())
        ).all()
    )
    return build_employee_day_sale_rows(sales)


def build_employee_sale_detail_snapshot(sale) -> EmployeeSaleDetailSnapshot:
    sale_datetime = getattr(sale, "confirmada_at", None) or getattr(sale, "created_at", None)
    if sale_datetime is not None and sale_datetime.tzinfo is not None:
        sale_datetime = sale_datetime.astimezone()
    time_label = sale_datetime.strftime("%H:%M") if sale_datetime is not None else "--:--"
    client = getattr(sale, "cliente", None)
    client_name = getattr(client, "nombre", None) or "Mostrador"
    detail_rows: list[EmployeeSaleDetailLineRow] = []
    pieces = 0
    for detail in getattr(sale, "detalles", ()) or ():
        variante = getattr(detail, "variante", None)
        producto = getattr(variante, "producto", None) if variante is not None else None
        sku = getattr(variante, "sku", None) or getattr(detail, "sku_snapshot", None) or "SIN SKU"
        product_name = getattr(producto, "nombre", None) or getattr(detail, "descripcion_snapshot", None) or "Producto"
        cantidad = int(getattr(detail, "cantidad", 0) or 0)
        pieces += cantidad
        unit_price = Decimal(str(getattr(detail, "precio_unitario", Decimal("0.00")) or Decimal("0.00"))).quantize(
            Decimal("0.01")
        )
        subtotal = Decimal(str(getattr(detail, "subtotal_linea", Decimal("0.00")) or Decimal("0.00"))).quantize(
            Decimal("0.01")
        )
        detail_rows.append(
            EmployeeSaleDetailLineRow(
                values=(
                    sku,
                    product_name,
                    cantidad,
                    unit_price,
                    subtotal,
                )
            )
        )
    total = Decimal(str(getattr(sale, "total", Decimal("0.00")) or Decimal("0.00"))).quantize(Decimal("0.01"))
    return EmployeeSaleDetailSnapshot(
        sale_id=int(getattr(sale, "id")),
        folio=str(getattr(sale, "folio", "") or ""),
        time_label=time_label,
        client_name=client_name,
        pieces=pieces,
        total=total,
        rows=tuple(detail_rows),
    )


def load_employee_sale_detail_snapshot(session, *, sale_id: int) -> EmployeeSaleDetailSnapshot:
    sale = session.scalar(
        select(Venta)
        .options(
            selectinload(Venta.cliente),
            selectinload(Venta.detalles)
            .selectinload(VentaDetalle.variante)
            .selectinload(Variante.producto),
        )
        .where(
            Venta.id == sale_id,
            Venta.estado == EstadoVenta.CONFIRMADA,
            Venta.credit_mode == ModoOrigenVenta.EMPLOYEE,
        )
    )
    if sale is None:
        raise ValueError("No se encontro el ticket seleccionado.")
    return build_employee_sale_detail_snapshot(sale)
