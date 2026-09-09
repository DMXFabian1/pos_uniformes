"""Nómina de empleadas: cuánto se le paga a cada una y cuándo.

Regla (Daniel, 2026-09-08): por ciclo de pago (7 días de calendario)
    total = sueldo_base + comisiones × tarifa_comision − faltas × descuento_falta
Los valores viven en `caja_parametros` (hoy 1300 + 2/comisión − 216.67/falta).

Al registrar el pago se guarda el desglose en `empleada_pago`, se anota el
evento "pago" del calendario y el corte de caja lo descuenta del cajón.
Solo Daniel (VEND-1) y su papá (ENC-1) registran pagos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from pos_uniformes.services.corte_caja_service import ParametrosCaja, cargar_parametros
from pos_uniformes.services.calendario_empleadas_service import (
    ENCARGADO_CODE,
    HorarioEmpleada,
    cargar_horario,
    comisiones_desde_ultimo_pago,
    es_dia_trabajado,
    faltas_en_rango,
    fecha_proximo_pago,
    quienes_descansan,
    registrar_pago,
)

DIAS_POR_SEMANA = 6  # tarifa por día = sueldo_base / 6

_CENT = Decimal("0.01")
OWNER_CODE = "VEND-1"
AUTO_CODE = "AUTO"  # el corte automático (tarea programada) también registra pagos
QUIEN_PUEDE_PAGAR = frozenset({OWNER_CODE, ENCARGADO_CODE, AUTO_CODE})


def puede_pagar(employee_code: str | None) -> bool:
    return str(employee_code or "").strip().upper() in QUIEN_PUEDE_PAGAR


@dataclass(frozen=True)
class DetallePago:
    employee_code: str
    desde: date | None      # primer día que cubre (día siguiente al último pago)
    hasta: date             # último día que cubre (el día del pago)
    comisiones: int
    sueldo_base: Decimal    # modo por_dia: días × tarifa_dia
    tarifa_comision: Decimal
    faltas: int
    descuento_falta: Decimal
    dias_trabajados: int | None = None   # solo modo por_dia
    tarifa_dia: Decimal | None = None    # solo modo por_dia

    @property
    def por_dia(self) -> bool:
        return self.dias_trabajados is not None

    @property
    def monto_comisiones(self) -> Decimal:
        return (self.tarifa_comision * self.comisiones).quantize(_CENT)

    @property
    def descuento_faltas(self) -> Decimal:
        return (self.descuento_falta * self.faltas).quantize(_CENT)

    @property
    def total(self) -> Decimal:
        total = self.sueldo_base + self.monto_comisiones - self.descuento_faltas
        return max(total, Decimal("0.00")).quantize(_CENT)


@dataclass(frozen=True)
class AvisoPago:
    employee_code: str
    employee_name: str
    fecha_pago: date | None  # None = nunca se le ha pagado (sin ciclo)
    dias_para_pago: int | None
    comisiones: int
    total_estimado: Decimal


# ─── Lógica pura ─────────────────────────────────────────────────────────

def calcular_pago(
    horario: HorarioEmpleada,
    *,
    comisiones: int,
    params: ParametrosCaja,
    hasta: date,
) -> DetallePago:
    desde = horario.fecha_ultimo_pago + timedelta(days=1) if horario.fecha_ultimo_pago else None
    inicio = desde or (hasta - timedelta(days=horario.ciclo_dias_pago - 1))
    if horario.por_dia:
        # Cobra solo los días que trabajó (marcados en su patrón o apuntados
        # como "trabajó"); no hay faltas: el día que no vino no se paga.
        tarifa_dia = (params.sueldo_base / DIAS_POR_SEMANA).quantize(_CENT)
        dias = 0
        dia = inicio
        while dia <= hasta:
            if es_dia_trabajado(horario, dia):
                dias += 1
            dia += timedelta(days=1)
        return DetallePago(
            employee_code=horario.employee_code,
            desde=desde,
            hasta=hasta,
            comisiones=int(comisiones or 0),
            sueldo_base=(tarifa_dia * dias).quantize(_CENT),
            tarifa_comision=params.tarifa_comision,
            faltas=0,
            descuento_falta=Decimal("0.00"),
            dias_trabajados=dias,
            tarifa_dia=tarifa_dia,
        )
    faltas = faltas_en_rango(horario, inicio, hasta)
    return DetallePago(
        employee_code=horario.employee_code,
        desde=desde,
        hasta=hasta,
        comisiones=int(comisiones or 0),
        sueldo_base=params.sueldo_base,
        tarifa_comision=params.tarifa_comision,
        faltas=faltas,
        descuento_falta=params.descuento_falta,
    )


# ─── Acceso a datos ──────────────────────────────────────────────────────

def ve_privados(quien: str | None) -> bool:
    """Solo Daniel ve los movimientos que él marcó como privados. Para el
    encargado esas ventas no existen: ni su dinero ni sus comisiones."""
    return quien is None or str(quien).strip().upper() == OWNER_CODE


def pago_pendiente(session, employee_code: str, hoy: date | None = None, *, para: str | None = None) -> DetallePago:
    """Lo que se le pagaría hoy a la empleada (sin registrar nada).

    `para` = quién está mirando/pagando: si es el encargado, las comisiones
    de los movimientos privados no se cuentan."""
    hoy = hoy or date.today()
    horario = cargar_horario(session, employee_code)
    comisiones = comisiones_desde_ultimo_pago(
        session, employee_code, horario, incluir_privadas=ve_privados(para)
    )
    return calcular_pago(horario, comisiones=comisiones, params=cargar_parametros(session), hasta=hoy)


def registrar_pago_con_monto(session, employee_code: str, *, creado_por: str, fecha: date | None = None, momento: datetime | None = None):
    """Calcula, guarda el desglose y anota el pago en el calendario.

    Devuelve la fila `EmpleadaPago`. Lanza PermissionError si quien paga no
    es el dueño ni el encargado."""
    from pos_uniformes.database.models import Empleada, EmpleadaPago

    if not puede_pagar(creado_por):
        raise PermissionError("Solo el dueño o el encargado registran pagos.")
    fecha = fecha or date.today()
    code = str(employee_code).strip().upper()
    detalle = pago_pendiente(session, code, fecha, para=creado_por)
    emp = session.query(Empleada).filter(Empleada.codigo == code).first()
    pago = EmpleadaPago(
        employee_code=code,
        employee_name=(emp.nombre_completo if emp else code),
        fecha=fecha,
        desde=detalle.desde,
        hasta=detalle.hasta,
        comisiones=detalle.comisiones,
        sueldo_base=detalle.sueldo_base,
        tarifa_comision=detalle.tarifa_comision,
        monto_comisiones=detalle.monto_comisiones,
        faltas=detalle.faltas,
        descuento_faltas=detalle.descuento_faltas,
        total=detalle.total,
        creado_por=str(creado_por).strip().upper(),
        dias_trabajados=detalle.dias_trabajados,
        tarifa_dia=detalle.tarifa_dia,
        # Explícito (no server_default). El corte automático pasa `momento`
        # = la hora del corte, así el pago queda DENTRO del periodo que cierra
        # (bug 2026-09-09: el bot fijaba la hora antes de registrar el pago y
        # el pago de Fanny no se restó de la venta).
        created_at=momento or datetime.now().astimezone(),
    )
    session.add(pago)
    registrar_pago(session, code, fecha)  # commit incluido
    return pago


def deshacer_pago(session, pago_id: int, *, creado_por: str) -> dict:
    """Quita un pago registrado por error (SOLO Daniel, VEND-1).

    Borra la fila `empleada_pago`, quita la marca 💵 de ese día en el
    calendario (si no hay otro pago ese día) y regresa `fecha_ultimo_pago`
    de la empleada al día anterior al periodo que cubría el pago — así el
    siguiente corte/pago vuelve a contar ese tramo completo.
    """
    from pos_uniformes.database.models import EmpleadaEvento, EmpleadaHorario, EmpleadaPago
    from pos_uniformes.services.calendario_empleadas_service import PAGO

    if str(creado_por or "").strip().upper() != "VEND-1":
        raise PermissionError("Solo Daniel puede deshacer pagos.")
    pago = session.get(EmpleadaPago, int(pago_id))
    if pago is None:
        raise ValueError("Ese pago ya no existe.")
    code = str(pago.employee_code).upper()
    anterior = (pago.desde - timedelta(days=1)) if pago.desde else None
    horario = session.get(EmpleadaHorario, code)
    fecha_restaurada = None
    if horario is not None and horario.fecha_ultimo_pago == pago.fecha:
        horario.fecha_ultimo_pago = anterior
        fecha_restaurada = anterior
    otro_mismo_dia = (
        session.query(EmpleadaPago)
        .filter(EmpleadaPago.employee_code == code, EmpleadaPago.fecha == pago.fecha, EmpleadaPago.id != pago.id)
        .first()
    )
    if otro_mismo_dia is None:
        for ev in session.query(EmpleadaEvento).filter(
            EmpleadaEvento.employee_code == code, EmpleadaEvento.fecha == pago.fecha, EmpleadaEvento.tipo == PAGO
        ).all():
            session.delete(ev)
    resumen = {"employee_code": code, "employee_name": pago.employee_name, "fecha": pago.fecha, "total": pago.total, "fecha_ultimo_pago": fecha_restaurada}
    session.delete(pago)
    session.commit()
    return resumen


def ultimo_pago_registrado(session, employee_code: str):
    from pos_uniformes.database.models import EmpleadaPago

    return (
        session.query(EmpleadaPago)
        .filter(EmpleadaPago.employee_code == str(employee_code).strip().upper())
        .order_by(EmpleadaPago.created_at.desc())
        .first()
    )


def _empleadas_activas(session) -> list:
    from pos_uniformes.database.models import Empleada

    return list(
        session.query(Empleada)
        .filter(Empleada.activo.is_(True))
        .order_by(Empleada.nombre_completo)
        .all()
    )


def avisos_de_pago(session, hoy: date | None = None, dias: int = 7, *, para: str | None = None) -> list[AvisoPago]:
    """Empleadas a las que les toca pago en los próximos `dias` (incluye hoy y
    atrasados), con lo que llevan acumulado. Ordenado por fecha de pago."""
    hoy = hoy or date.today()
    params = cargar_parametros(session)
    avisos: list[AvisoPago] = []
    for emp in _empleadas_activas(session):
        if emp.codigo.upper() in QUIEN_PUEDE_PAGAR:
            continue
        horario = cargar_horario(session, emp.codigo)
        proximo = fecha_proximo_pago(horario, hoy)
        if proximo is not None and (proximo - hoy).days > dias:
            continue
        comisiones = comisiones_desde_ultimo_pago(
            session, emp.codigo, horario, incluir_privadas=ve_privados(para)
        )
        detalle = calcular_pago(horario, comisiones=comisiones, params=params, hasta=max(hoy, proximo or hoy))
        avisos.append(
            AvisoPago(
                employee_code=emp.codigo.upper(),
                employee_name=emp.nombre_completo,
                fecha_pago=proximo,
                dias_para_pago=(proximo - hoy).days if proximo else None,
                comisiones=comisiones,
                total_estimado=detalle.total,
            )
        )
    avisos.sort(key=lambda a: (a.fecha_pago is None, a.fecha_pago or hoy, a.employee_name))
    return avisos


@dataclass(frozen=True)
class ResumenEncargado:
    descansan_hoy: list[str]
    descansan_manana: list[str]
    pagos: list[AvisoPago]


def resumen_para_encargado(session, hoy: date | None = None) -> ResumenEncargado:
    """Lo que el encargado necesita ver al entrar: quién descansa hoy y
    mañana, y a quién le toca pago esta semana y cuánto."""
    from pos_uniformes.services.calendario_empleadas_service import cargar_horarios_todos

    hoy = hoy or date.today()
    horarios = cargar_horarios_todos(session)
    nombres = {e.codigo.upper(): e.nombre_completo for e in _empleadas_activas(session)}

    def _nombres(codes: list[str]) -> list[str]:
        return [nombres.get(c, c) for c in codes if c in nombres]

    return ResumenEncargado(
        descansan_hoy=_nombres(quienes_descansan(horarios, hoy)),
        descansan_manana=_nombres(quienes_descansan(horarios, hoy + timedelta(days=1))),
        pagos=avisos_de_pago(session, hoy, para=ENCARGADO_CODE),
    )


_DIAS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def cuando_pago(a: AvisoPago) -> str:
    """'HOY' · 'mañana' · 'viernes 11/09' · 'ATRASADO 2 día(s)' · 'sin fecha…' (en español, no %A)."""
    if a.fecha_pago is None:
        return "sin fecha (nunca se le ha pagado)"
    if a.dias_para_pago is not None and a.dias_para_pago < 0:
        return f"ATRASADO {-a.dias_para_pago} día(s)"
    if a.dias_para_pago == 0:
        return "HOY"
    if a.dias_para_pago == 1:
        return "mañana"
    return f"{_DIAS_ES[a.fecha_pago.weekday()]} {a.fecha_pago.strftime('%d/%m')}"


def texto_resumen_encargado(resumen: ResumenEncargado, hoy: date | None = None) -> str:
    """Texto corto para la pantalla del encargado / la app del celular."""
    hoy = hoy or date.today()
    partes = []
    partes.append("Hoy descansa: " + (", ".join(resumen.descansan_hoy) or "nadie"))
    partes.append("Mañana descansa: " + (", ".join(resumen.descansan_manana) or "nadie"))
    if resumen.pagos:
        lineas = []
        for a in resumen.pagos:
            cuando = cuando_pago(a)
            lineas.append(f"{a.employee_name}: {cuando} · {a.comisiones} comisiones · ${a.total_estimado:,.2f}")
        partes.append("Pagos: " + " | ".join(lineas))
    else:
        partes.append("Pagos: ninguno en los próximos 7 días")
    return "\n".join(partes)


# ─── Historial de pagos (vista del dueño) ────────────────────────────────

@dataclass(frozen=True)
class TotalEmpleada:
    employee_code: str
    employee_name: str
    pagos: int
    comisiones: int
    faltas: int
    monto_comisiones: Decimal
    descuento_faltas: Decimal
    total: Decimal


def listar_pagos(session, *, desde: date, hasta: date, employee_code: str | None = None) -> list:
    """Pagos registrados con fecha entre `desde` y `hasta` (inclusive), del
    más reciente al más viejo."""
    from pos_uniformes.database.models import EmpleadaPago

    q = session.query(EmpleadaPago).filter(EmpleadaPago.fecha >= desde, EmpleadaPago.fecha <= hasta)
    if employee_code:
        q = q.filter(EmpleadaPago.employee_code == str(employee_code).strip().upper())
    return list(q.order_by(EmpleadaPago.fecha.desc(), EmpleadaPago.id.desc()).all())


def resumir_pagos_por_empleada(pagos: list) -> list[TotalEmpleada]:
    """Totales por empleada (puro). Ordenado por total pagado, mayor primero."""
    acc: dict[str, dict] = {}
    for p in pagos:
        code = str(p.employee_code).upper()
        a = acc.setdefault(code, {
            "nombre": p.employee_name or code, "pagos": 0, "comisiones": 0, "faltas": 0,
            "monto_comisiones": Decimal("0.00"), "descuento_faltas": Decimal("0.00"), "total": Decimal("0.00"),
        })
        a["pagos"] += 1
        a["comisiones"] += int(p.comisiones or 0)
        a["faltas"] += int(p.faltas or 0)
        a["monto_comisiones"] += Decimal(str(p.monto_comisiones or 0))
        a["descuento_faltas"] += Decimal(str(p.descuento_faltas or 0))
        a["total"] += Decimal(str(p.total or 0))
    filas = [
        TotalEmpleada(
            employee_code=code,
            employee_name=a["nombre"],
            pagos=a["pagos"],
            comisiones=a["comisiones"],
            faltas=a["faltas"],
            monto_comisiones=a["monto_comisiones"].quantize(_CENT),
            descuento_faltas=a["descuento_faltas"].quantize(_CENT),
            total=a["total"].quantize(_CENT),
        )
        for code, a in acc.items()
    ]
    filas.sort(key=lambda t: (t.total, t.employee_name), reverse=True)
    return filas


def rango_mes(year: int, month: int) -> tuple[date, date]:
    primero = date(year, month, 1)
    siguiente = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return primero, siguiente - timedelta(days=1)
