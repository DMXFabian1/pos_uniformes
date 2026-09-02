"""La "Libreta": registro digital de operaciones del mostrador.

Cada venta/apartado de venta rápida se anota aquí, ligado al gafete de la
empleada en sesión. Dos vistas:
- Empleada: SUS operaciones, una por una, con piezas — sin montos.
- Dueño: todas las empleadas, con piezas y montos.

Ventanas: "hoy" (día local) y "semana" (calendario, lunes a domingo).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.utils.date_format import local_day_window


def ventana_hoy(reference: date | None = None) -> tuple[datetime, datetime]:
    return local_day_window(reference or date.today())


def ventana_semana(reference: date | None = None) -> tuple[datetime, datetime]:
    """Semana calendario: lunes 00:00 a domingo 23:59 (hora local)."""
    reference = reference or date.today()
    monday = reference - timedelta(days=reference.weekday())
    inicio, _ = local_day_window(monday)
    _, fin = local_day_window(monday + timedelta(days=6))
    return inicio, fin


def registrar_operacion(
    session,
    *,
    employee_code: str,
    employee_name: str,
    tipo: str,
    items: list[dict],
    monto_total: Decimal,
    descuento_empleada: bool = False,
    cliente: str | None = None,
    origen: str | None = None,
    created_at: datetime | None = None,
) -> LibretaVenta:
    """Anota una operación. `items` = líneas del carrito de venta rápida.

    created_at explícito: las operaciones encoladas offline conservan la hora
    en que se hicieron, no la del drenado."""
    detalle = [
        {
            "sku": str(it.get("sku", "")),
            "nombre": str(it.get("nombre", "")),
            "talla": str(it.get("talla", "")),
            "cantidad": int(it.get("cantidad", 0) or 0),
            "precio": str(it.get("precio", "0")),
            "subtotal": str(
                (Decimal(str(it.get("precio", 0) or 0)) * int(it.get("cantidad", 0) or 0)).quantize(
                    Decimal("0.01")
                )
            ),
        }
        for it in items
    ]
    entry = LibretaVenta(
        employee_code=str(employee_code).upper(),
        employee_name=employee_name or "",
        tipo=tipo,
        cliente=cliente,
        piezas=sum(line["cantidad"] for line in detalle),
        monto_total=Decimal(str(monto_total)).quantize(Decimal("0.01")),
        descuento_empleada=descuento_empleada,
        detalle=detalle,
        origen=origen,
    )
    if created_at is not None:
        entry.created_at = created_at
    session.add(entry)
    return entry


def listar_operaciones(
    session,
    *,
    desde: datetime,
    hasta: datetime,
    employee_code: str | None = None,
) -> list[LibretaVenta]:
    stmt = (
        select(LibretaVenta)
        .where(LibretaVenta.created_at >= desde, LibretaVenta.created_at <= hasta)
        .order_by(LibretaVenta.created_at.desc())
    )
    if employee_code:
        stmt = stmt.where(LibretaVenta.employee_code == str(employee_code).upper())
    return list(session.scalars(stmt).all())


@dataclass(frozen=True)
class ResumenEmpleada:
    employee_code: str
    employee_name: str
    operaciones: int
    piezas: int
    monto_total: Decimal


def resumir_por_empleada(rows: list[LibretaVenta]) -> list[ResumenEmpleada]:
    """Agregado para la vista del dueño, ordenado por piezas desc."""
    acc: dict[str, dict] = {}
    for row in rows:
        bucket = acc.setdefault(
            row.employee_code,
            {
                "name": row.employee_name,
                "operaciones": 0,
                "piezas": 0,
                "monto": Decimal("0.00"),
            },
        )
        bucket["operaciones"] += 1
        bucket["piezas"] += int(row.piezas or 0)
        bucket["monto"] = (bucket["monto"] + Decimal(str(row.monto_total or 0))).quantize(
            Decimal("0.01")
        )
        if row.employee_name:
            bucket["name"] = row.employee_name
    return sorted(
        (
            ResumenEmpleada(
                employee_code=code,
                employee_name=data["name"],
                operaciones=data["operaciones"],
                piezas=data["piezas"],
                monto_total=data["monto"],
            )
            for code, data in acc.items()
        ),
        key=lambda r: r.piezas,
        reverse=True,
    )


def describir_detalle(detalle: list[dict]) -> str:
    """'Pants T:6 x2 · Playera T:M x1' — resumen legible de las líneas."""
    parts = []
    for line in detalle or []:
        nombre = str(line.get("nombre", "")).strip() or str(line.get("sku", ""))
        talla = str(line.get("talla", "")).strip()
        cantidad = int(line.get("cantidad", 0) or 0)
        talla_txt = f" T:{talla}" if talla and talla != "-" else ""
        parts.append(f"{nombre}{talla_txt} x{cantidad}")
    return " · ".join(parts)
