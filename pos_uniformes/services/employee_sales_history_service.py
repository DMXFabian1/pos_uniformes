"""Historial puntual de operaciones por empleada, día y detalle de la operación.

2026-11-12, Daniel: «la caja antigua ya no es de utilidad, todo lo demás
corre en libreta y kioskos» → «Pantallas con datos viejos». Antes leía la
tabla `venta` de la Caja antigua; ahora lee la Libreta (`LibretaVenta`) con
el criterio del ranking: las operaciones que VENDIÓ la empleada (venta y
apartado, `cuenta_como_operacion`). «Ver ticket» enseña el detalle de la
operación de la Libreta (sus líneas guardadas en `detalle`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.utils.date_format import local_day_window

_CENT = Decimal("0.01")


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


def _dinero(valor) -> Decimal:
    try:
        return Decimal(str(valor if valor is not None else 0)).quantize(_CENT)
    except Exception:  # noqa: BLE001 — dato raro: no tumba la pantalla
        return Decimal("0.00")


def _hora(operacion) -> str:
    momento = getattr(operacion, "created_at", None)
    if momento is not None and momento.tzinfo is not None:
        momento = momento.astimezone()
    return momento.strftime("%H:%M") if momento is not None else "--:--"


def folio_de_operacion(operacion) -> str:
    """El folio impreso en el ticket del kiosko (`3F9A-12BC`, de su
    `operacion_uuid`); las operaciones de antes sin uuid salen como `#id`.
    Un apartado lo dice, para no confundirlo con una venta."""
    from pos_uniformes.services.folio_venta_service import folio_corto

    uuid_ = getattr(operacion, "operacion_uuid", None)
    try:
        folio = folio_corto(uuid_) if uuid_ else f"#{getattr(operacion, 'id', '')}"
    except (ValueError, AttributeError, TypeError):
        folio = f"#{getattr(operacion, 'id', '')}"
    tipo = str(getattr(operacion, "tipo", None) or "venta")
    return folio if tipo == "venta" else f"{folio} ({tipo})"


def _cliente(operacion) -> str:
    return str(getattr(operacion, "cliente", None) or "").strip() or "Mostrador"


def build_employee_day_sale_rows(operaciones) -> tuple[EmployeeDaySaleRow, ...]:
    """Las operaciones del día de una empleada, en orden (puro). Solo lo que
    cuenta como operación, como el ranking."""
    from pos_uniformes.services.libreta_service import cuenta_como_operacion

    rows: list[EmployeeDaySaleRow] = []
    for operacion in operaciones or ():
        if not cuenta_como_operacion(operacion):
            continue
        rows.append(
            EmployeeDaySaleRow(
                sale_id=int(getattr(operacion, "id")),
                values=(
                    _hora(operacion),
                    folio_de_operacion(operacion),
                    _cliente(operacion),
                    int(getattr(operacion, "piezas", 0) or 0),
                    _dinero(getattr(operacion, "monto_total", None)),
                ),
            )
        )
    return tuple(rows)


def list_employee_day_sale_rows(session, *, employee_code: str, target_day: date) -> tuple[EmployeeDaySaleRow, ...]:
    from pos_uniformes.services.libreta_service import predicado_operacion

    day_start, day_end = local_day_window(target_day)
    operaciones = session.scalars(
        select(LibretaVenta)
        .where(
            predicado_operacion(),
            func.upper(LibretaVenta.employee_code) == str(employee_code).upper(),
            LibretaVenta.created_at >= day_start,
            LibretaVenta.created_at < day_end,
        )
        .order_by(LibretaVenta.created_at.asc(), LibretaVenta.id.asc())
    ).all()
    return build_employee_day_sale_rows(operaciones)


def build_employee_sale_detail_snapshot(operacion) -> EmployeeSaleDetailSnapshot:
    """El detalle de una operación de la Libreta, con las líneas que guardó
    el kiosko al cobrar (puro)."""
    detail_rows: list[EmployeeSaleDetailLineRow] = []
    piezas_lineas = 0
    for linea in getattr(operacion, "detalle", None) or ():
        if not isinstance(linea, dict):
            continue
        cantidad = int(linea.get("cantidad") or 0)
        piezas_lineas += cantidad
        precio = _dinero(linea.get("precio"))
        subtotal = _dinero(linea.get("subtotal")) if linea.get("subtotal") is not None else (precio * cantidad).quantize(_CENT)
        nombre = str(linea.get("nombre") or "").strip() or "Producto"
        talla = str(linea.get("talla") or "").strip()
        if talla:
            nombre = f"{nombre} · talla {talla}"
        detail_rows.append(
            EmployeeSaleDetailLineRow(
                values=(
                    str(linea.get("sku") or "").strip() or "SIN SKU",
                    nombre,
                    cantidad,
                    precio,
                    subtotal,
                )
            )
        )
    return EmployeeSaleDetailSnapshot(
        sale_id=int(getattr(operacion, "id")),
        folio=folio_de_operacion(operacion),
        time_label=_hora(operacion),
        client_name=_cliente(operacion),
        pieces=int(getattr(operacion, "piezas", 0) or 0) or piezas_lineas,
        total=_dinero(getattr(operacion, "monto_total", None)),
        rows=tuple(detail_rows),
    )


def load_employee_sale_detail_snapshot(session, *, sale_id: int) -> EmployeeSaleDetailSnapshot:
    operacion = session.get(LibretaVenta, int(sale_id))
    if operacion is None:
        raise ValueError("Esta operacion ya no esta en la Libreta (se borro o se anulo).")
    return build_employee_sale_detail_snapshot(operacion)
