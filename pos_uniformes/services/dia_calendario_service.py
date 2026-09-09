"""Detalle de un día del calendario compartido del kiosko + consulta de pago con gafete.

- `resumen_dia`: quién descansa, a quién le toca pago y qué conteos caen ese día.
- `vista_de_pagos`: al escanear un gafete, qué se puede ver:
    * empleada → SOLO su pago pendiente (desglose y cuándo le toca);
    * Daniel (VEND-1) o su papá (ENC-1) → el de todas las activas.
  Cualquier otro código (producto, gafete de baja, vacío) → None.

Nada de aquí registra ni cambia datos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

DIAS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES_ES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def fecha_en_palabras(fecha: date) -> str:
    return f"{DIAS_ES[fecha.weekday()].capitalize()} {fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


@dataclass(frozen=True)
class ResumenDia:
    fecha: date
    descansan: list[str] = field(default_factory=list)   # nombres
    pagos: list[str] = field(default_factory=list)       # nombres con día de pago
    conteos: list = field(default_factory=list)          # EstadoCalendarioConteo

    @property
    def vacio(self) -> bool:
        return not (self.descansan or self.pagos or self.conteos)


def resumen_dia(session, fecha: date, hoy: date | None = None) -> ResumenDia:
    """Lo que el calendario muestra de ese día, sin truncar (la celda corta a 3)."""
    from pos_uniformes.services.calendario_empleadas_service import DESCANSO, PAGO, chips_calendario_mes

    hoy = hoy or date.today()
    descansan: list[str] = []
    pagos: list[str] = []
    try:
        chips = chips_calendario_mes(session, fecha.year, fecha.month, hoy).get(fecha, [])
    except Exception:  # noqa: BLE001 — tablas sin migrar
        session.rollback()
        chips = []
    for tipo, nombre in chips:
        destino = descansan if tipo == DESCANSO else pagos if tipo == PAGO else None
        if destino is not None and nombre not in destino:
            destino.append(nombre)
    conteos: list = []
    try:
        from pos_uniformes.services.conteo_calendario_service import (
            agrupar_calendario_por_dia,
            obtener_calendario_conteo,
        )

        estados = obtener_calendario_conteo(session)
        conteos = agrupar_calendario_por_dia(estados, fecha.year, fecha.month).get(fecha.day, [])
    except Exception:  # noqa: BLE001
        session.rollback()
    return ResumenDia(fecha=fecha, descansan=descansan, pagos=pagos, conteos=list(conteos))


@dataclass(frozen=True)
class PagoVista:
    employee_code: str
    employee_name: str
    detalle: object            # nomina_service.DetallePago
    proximo_pago: date | None
    configurado: bool


@dataclass(frozen=True)
class VistaPagos:
    todas: bool                 # True = la vio el dueño/encargado
    quien: str                  # nombre de quien escaneó
    pagos: list[PagoVista]


def _nombre_corto(nombre: str | None, code: str) -> str:
    return (nombre or code).split()[0] if (nombre or code) else code


def _pago_vista(session, emp, hoy: date) -> PagoVista:
    from pos_uniformes.services.calendario_empleadas_service import cargar_horario, fecha_proximo_pago
    from pos_uniformes.services.nomina_service import pago_pendiente

    code = str(emp.codigo).upper()
    horario = cargar_horario(session, code)
    return PagoVista(
        employee_code=code,
        employee_name=emp.nombre_completo or code,
        detalle=pago_pendiente(session, code, hoy),
        proximo_pago=fecha_proximo_pago(horario, hoy),
        configurado=bool(getattr(horario, "configurado", True)),
    )


def vista_de_pagos(session, raw_scan: str, hoy: date | None = None) -> VistaPagos | None:
    """Qué pagos puede ver quien escaneó. None si el código no es un gafete activo."""
    from pos_uniformes.database.models import Empleada
    from pos_uniformes.services.employee_identity_service import EmployeeIdentityService
    from pos_uniformes.services.nomina_service import QUIEN_PUEDE_PAGAR, puede_pagar

    hoy = hoy or date.today()
    try:
        code = EmployeeIdentityService.normalize_employee_code(raw_scan or "")
    except ValueError:
        return None
    activas = session.query(Empleada).filter(Empleada.activo.is_(True)).order_by(Empleada.nombre_completo).all()
    por_code = {str(e.codigo).upper(): e for e in activas}
    quien = por_code.get(code)
    if quien is None:
        return None
    if puede_pagar(code):
        pagos = [
            _pago_vista(session, e, hoy)
            for c, e in por_code.items()
            if c not in QUIEN_PUEDE_PAGAR
        ]
        return VistaPagos(todas=True, quien=_nombre_corto(quien.nombre_completo, code), pagos=pagos)
    return VistaPagos(todas=False, quien=_nombre_corto(quien.nombre_completo, code), pagos=[_pago_vista(session, quien, hoy)])


def lineas_pago(p: PagoVista, hoy: date | None = None) -> list[str]:
    """Desglose en palabras llanas (mismo criterio que el ticket de pago)."""
    hoy = hoy or date.today()
    d = p.detalle
    lineas: list[str] = []
    if not p.configurado:
        lineas.append("Sin horario configurado: pídele a Daniel que lo capture.")
    if getattr(d, "por_dia", False):
        lineas.append(f"{d.dias_trabajados} día(s) × ${Decimal(d.tarifa_dia):,.2f} = ${Decimal(d.sueldo_base):,.2f}")
    else:
        lineas.append(f"Sueldo: ${Decimal(d.sueldo_base):,.2f}")
    lineas.append(f"{d.comisiones} comisiones × ${Decimal(d.tarifa_comision):,.2f} = ${Decimal(d.monto_comisiones):,.2f}")
    if int(d.faltas or 0):
        lineas.append(f"{d.faltas} falta(s): −${Decimal(d.descuento_faltas):,.2f}")
    lineas.append(f"TOTAL HOY: ${Decimal(d.total):,.2f}")
    if p.proximo_pago is not None:
        if p.proximo_pago == hoy:
            cuando = "hoy"
        elif p.proximo_pago < hoy:
            cuando = f"desde el {DIAS_ES[p.proximo_pago.weekday()]} {p.proximo_pago.day} (atrasado)"
        else:
            cuando = f"el {DIAS_ES[p.proximo_pago.weekday()]} {p.proximo_pago.day} de {MESES_ES[p.proximo_pago.month - 1]}"
        lineas.append(f"Te toca cobrar {cuando}.")
    return lineas
