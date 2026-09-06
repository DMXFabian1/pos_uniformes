"""La "Libreta": registro digital de operaciones del mostrador.

Cada venta/apartado de venta rápida se anota aquí, ligado al gafete de la
empleada en sesión. Dos vistas:
- Empleada: SUS operaciones, una por una, con piezas — sin montos.
- Dueño: todas las empleadas, con piezas y montos.

Ventanas: "hoy" (día local) y "semana" (calendario, lunes a domingo).
"""

from __future__ import annotations

import re
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


def ventana_semana_anterior(reference: date | None = None) -> tuple[datetime, datetime]:
    """La semana calendario ANTERIOR completa (para verificar comisiones el
    día de pago, cuando la semana actual ya se reinició)."""
    reference = reference or date.today()
    return ventana_semana(reference - timedelta(days=7))


def ventana_ciclo(fecha_ultimo_pago: date | None) -> tuple[datetime, datetime]:
    """Del día SIGUIENTE al último pago hasta hoy: el desglose que respalda
    el banner "Comisiones desde tu último pago" (la vista para pagar).
    Sin pago registrado aún: los últimos 90 días."""
    hoy = date.today()
    inicio_dia = (
        fecha_ultimo_pago + timedelta(days=1)
        if fecha_ultimo_pago is not None
        else hoy - timedelta(days=90)
    )
    inicio, _ = local_day_window(inicio_dia)
    _, fin = local_day_window(hoy)
    return inicio, fin


def ventana_rango(desde: date, hasta: date) -> tuple[datetime, datetime]:
    """Rango libre de fechas (inclusive); si vienen volteadas, se corrigen."""
    if hasta < desde:
        desde, hasta = hasta, desde
    inicio, _ = local_day_window(desde)
    _, fin = local_day_window(hasta)
    return inicio, fin


def filtrar_operaciones(
    rows: list,
    *,
    tipo: str | None = None,
    employee_code: str | None = None,
    solo_tarjeta: bool = False,
) -> list:
    """Filtros en memoria para la vista del dueño (tipo, empleada, tarjeta)."""
    result = list(rows)
    if tipo:
        result = [r for r in result if str(r.tipo) == tipo]
    if employee_code:
        code = str(employee_code).upper()
        result = [r for r in result if str(r.employee_code).upper() == code]
    if solo_tarjeta:
        result = [r for r in result if bool(getattr(r, "pago_tarjeta", False))]
    return result


def lineas_detalle(detalle: list[dict], *, con_precios: bool) -> list[list[str]]:
    """Filas [producto, talla, cantidad(, precio, subtotal)] para el diálogo
    de detalle de una operación. Sin precios para la vista de empleada."""
    filas: list[list[str]] = []
    for line in detalle or []:
        nombre = str(line.get("nombre", "")).strip() or str(line.get("sku", ""))
        talla = str(line.get("talla", "")).strip() or "-"
        cantidad = str(int(line.get("cantidad", 0) or 0))
        if con_precios:
            precio = Decimal(str(line.get("precio", 0) or 0)).quantize(Decimal("0.01"))
            subtotal = Decimal(str(line.get("subtotal", 0) or 0)).quantize(Decimal("0.01"))
            filas.append([nombre, talla, cantidad, f"${precio:,.2f}", f"${subtotal:,.2f}"])
        else:
            filas.append([nombre, talla, cantidad])
    return filas


# Comisión de la terminal bancaria (pagos con tarjeta): única fuente del
# porcentaje para venta rápida, abonos y la Libreta.
TERMINAL_COMMISSION_PERCENT = Decimal("4.5")


def aplicar_comision_terminal(monto: Decimal) -> Decimal:
    """Monto tras descontar la comisión de terminal, con la regla de
    redondeo de la tienda (sale_rounding_service)."""
    from pos_uniformes.services.sale_rounding_service import resolve_sale_rounding

    factor = (Decimal("100") - TERMINAL_COMMISSION_PERCENT) / Decimal("100")
    con_comision = (Decimal(str(monto)) * factor).quantize(Decimal("0.01"))
    return resolve_sale_rounding(con_comision).collected_total


# Regla de comisiones de Daniel: el conjunto 3pz vale 2 comisiones por
# unidad (corregido 2026-09-06: antes contaba 3); TODO lo demás (2pz
# incluido, prendas sueltas) vale 1 por unidad.
COMISIONES_3PZ = 2
_RE_3PZ = re.compile(r"3\s*pz", re.IGNORECASE)


def comisiones_de_linea(nombre: str, cantidad: int) -> int:
    factor = COMISIONES_3PZ if _RE_3PZ.search(str(nombre or "")) else 1
    return factor * int(cantidad or 0)


def comisiones_de_items(items: list[dict]) -> int:
    return sum(
        comisiones_de_linea(it.get("nombre", ""), int(it.get("cantidad", 0) or 0))
        for it in items or []
    )


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
    pago_tarjeta: bool = False,
    monto_neto: Decimal | None = None,
    comisiones: int | None = None,
) -> LibretaVenta:
    """Anota una operación. `items` = líneas del carrito de venta rápida.

    created_at explícito: las operaciones encoladas offline conservan la hora
    en que se hicieron, no la del drenado.
    comisiones None → se calculan de los items (3pz=2, resto 1/unidad); los
    abonos deben pasar comisiones=0 explícito.
    monto_neto None → igual a monto_total (efectivo)."""
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
    monto_total = Decimal(str(monto_total)).quantize(Decimal("0.01"))
    entry = LibretaVenta(
        employee_code=str(employee_code).upper(),
        employee_name=employee_name or "",
        tipo=tipo,
        cliente=cliente,
        piezas=sum(line["cantidad"] for line in detalle),
        comisiones=comisiones_de_items(items) if comisiones is None else int(comisiones),
        monto_total=monto_total,
        monto_neto=(
            monto_total if monto_neto is None else Decimal(str(monto_neto)).quantize(Decimal("0.01"))
        ),
        pago_tarjeta=pago_tarjeta,
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
    comisiones: int
    monto_total: Decimal


def resumir_por_empleada(rows: list[LibretaVenta]) -> list[ResumenEmpleada]:
    """Agregado para la vista del dueño, ordenado por comisiones desc."""
    acc: dict[str, dict] = {}
    for row in rows:
        bucket = acc.setdefault(
            row.employee_code,
            {
                "name": row.employee_name,
                "operaciones": 0,
                "piezas": 0,
                "comisiones": 0,
                "monto": Decimal("0.00"),
            },
        )
        bucket["operaciones"] += 1
        bucket["piezas"] += int(row.piezas or 0)
        bucket["comisiones"] += int(getattr(row, "comisiones", 0) or 0)
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
                comisiones=data["comisiones"],
                monto_total=data["monto"],
            )
            for code, data in acc.items()
        ),
        key=lambda r: (r.comisiones, r.piezas),
        reverse=True,
    )


# %a depende del locale (daría "Mon"); nombres propios en español.
_DIAS_SEMANA = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


@dataclass(frozen=True)
class CorteDia:
    dia: date
    dia_label: str
    operaciones: int
    piezas: int
    monto_ventas: Decimal
    monto_neto_ventas: Decimal
    monto_apartados: Decimal
    monto_abonos: Decimal
    # Efectivo que debe haber en el cajón: ventas + abonos pagados en
    # efectivo. Lo de tarjeta no está en caja (llega por la terminal) y el
    # apartado no es dinero recibido (su dinero entra vía abonos).
    monto_en_caja: Decimal


def resumir_por_dia(rows: list[LibretaVenta]) -> list[CorteDia]:
    """Corte diario para la vista del dueño: cuánto se vendió cada día.

    - Ventas: lo cobrado, y el neto tras la comisión de terminal (4.5% en
      pagos con tarjeta; igual al cobrado en efectivo).
    - Apartados: comprometido, no cobrado completo.
    - Abonos: dinero cobrado de apartados.
    Días ordenados del más reciente al más viejo (hora local)."""
    acc: dict[date, dict] = {}
    for row in rows:
        created = row.created_at
        local_dt = created.astimezone() if created.tzinfo is not None else created
        dia = local_dt.date()
        bucket = acc.setdefault(
            dia,
            {
                "operaciones": 0,
                "piezas": 0,
                "ventas": Decimal("0.00"),
                "neto": Decimal("0.00"),
                "apartados": Decimal("0.00"),
                "abonos": Decimal("0.00"),
                "en_caja": Decimal("0.00"),
            },
        )
        bucket["operaciones"] += 1
        bucket["piezas"] += int(row.piezas or 0)
        monto = Decimal(str(row.monto_total or 0))
        neto = Decimal(str(getattr(row, "monto_neto", None) or monto))
        tipo = str(row.tipo)
        pago_tarjeta = bool(getattr(row, "pago_tarjeta", False))
        if tipo == "apartado":
            bucket["apartados"] = (bucket["apartados"] + monto).quantize(Decimal("0.01"))
        elif tipo == "abono":
            bucket["abonos"] = (bucket["abonos"] + neto).quantize(Decimal("0.01"))
            if not pago_tarjeta:
                bucket["en_caja"] = (bucket["en_caja"] + monto).quantize(Decimal("0.01"))
        else:
            bucket["ventas"] = (bucket["ventas"] + monto).quantize(Decimal("0.01"))
            bucket["neto"] = (bucket["neto"] + neto).quantize(Decimal("0.01"))
            if not pago_tarjeta:
                bucket["en_caja"] = (bucket["en_caja"] + monto).quantize(Decimal("0.01"))
    return [
        CorteDia(
            dia=dia,
            dia_label=f"{_DIAS_SEMANA[dia.weekday()]} {dia.strftime('%d/%m')}",
            operaciones=data["operaciones"],
            piezas=data["piezas"],
            monto_ventas=data["ventas"],
            monto_neto_ventas=data["neto"],
            monto_apartados=data["apartados"],
            monto_abonos=data["abonos"],
            monto_en_caja=data["en_caja"],
        )
        for dia, data in sorted(acc.items(), key=lambda kv: kv[0], reverse=True)
    ]


def eliminar_operacion(session, operacion_id: int) -> bool:
    """Borra un registro de la Libreta (corrección del dueño: se imprimió
    por error, venta que no se concretó). Devuelve True si existía."""
    entry = session.get(LibretaVenta, int(operacion_id))
    if entry is None:
        return False
    session.delete(entry)
    return True


def cambiar_pago_tarjeta(session, operacion_id: int, tarjeta: bool):
    """Corrección del dueño: la empleada olvidó marcar "pagó con tarjeta"
    (o lo marcó de más). Cambia la bandera y RECALCULA el neto con la
    misma regla que la venta: 4.5% por producto sobre el precio cobrado
    (ya con descuento de empleada si lo hubo), redondeado; efectivo → neto
    = total. Devuelve el registro o None si no existe."""
    entry = session.get(LibretaVenta, int(operacion_id))
    if entry is None:
        return None
    total = Decimal(str(entry.monto_total or 0)).quantize(Decimal("0.01"))
    if not tarjeta:
        neto = total
    else:
        detalle = list(entry.detalle or [])
        if detalle:
            factor_desc = (
                Decimal("0.95") if entry.descuento_empleada else Decimal("1")
            )
            neto = Decimal("0.00")
            for line in detalle:
                unit = Decimal(str(line.get("precio", 0) or 0))
                unit = (unit * factor_desc).quantize(Decimal("0.01"))
                neto += aplicar_comision_terminal(unit) * int(line.get("cantidad", 0) or 0)
            neto = neto.quantize(Decimal("0.01"))
        else:
            neto = aplicar_comision_terminal(total)  # abonos: sobre el monto
    entry.pago_tarjeta = bool(tarjeta)
    entry.monto_neto = neto
    session.commit()
    return entry


def filtrar_de_hoy(rows: list, reference: date | None = None) -> list:
    """Deja solo las operaciones del día local dado (default: hoy).

    Permite consultar UNA vez la ventana de la semana y derivar la vista
    'Hoy' en memoria (la meta semanal necesita la semana completa)."""
    reference = reference or date.today()
    result = []
    for row in rows:
        created = row.created_at
        local_dt = created.astimezone() if created.tzinfo is not None else created
        if local_dt.date() == reference:
            result.append(row)
    return result


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


def guardar_corte(
    session,
    *,
    fecha: date,
    monto_final: Decimal,
    operaciones: int,
    piezas: int,
    periodo_label: str = "HOY",
    nota: str = "",
    creado_por: str = "",
):
    """Registra el corte con SOLO la cifra final del dueño (sin esperado ni
    diferencia): el número oficial. Es lo que ve el encargado."""
    from pos_uniformes.database.models import LibretaCorte

    fila = LibretaCorte(
        fecha=fecha,
        periodo_label=periodo_label[:80],
        monto_final=monto_final,
        operaciones=int(operaciones),
        piezas=int(piezas),
        nota=(nota or None),
        creado_por=creado_por,
    )
    session.add(fila)
    session.commit()
    return fila


def listar_cortes(session, *, limit: int = 15):
    """Últimos cortes, el más reciente primero (vista del encargado)."""
    from pos_uniformes.database.models import LibretaCorte

    return (
        session.query(LibretaCorte)
        .order_by(LibretaCorte.fecha.desc(), LibretaCorte.id.desc())
        .limit(limit)
        .all()
    )
