"""Calendario de empleadas: descansos, faltas, pagos y comisiones del ciclo.

Reglas del negocio (definidas por Daniel):
- Descanso: un día FIJO de la semana por empleada (excepciones por evento).
- Pago: cada N días TRABAJADOS desde el último pago — una falta o un
  descanso extra recorren la fecha del próximo pago automáticamente.
- Un evento explícito del día ("falta", "descanso", "trabajo") le gana al
  patrón fijo del horario.

La lógica de fechas es pura (testeable sin base); las funciones con
`session` son los accesos a datos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

WEEKDAY_NAMES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

# Estados posibles de un día (para pintar el calendario).
TRABAJO = "trabajo"
DESCANSO = "descanso"
FALTA = "falta"
PAGO = "pago"

# Tope de búsqueda del próximo pago: si en 90 días no se junta el ciclo,
# algo está mal configurado y devolvemos None en vez de ciclar.
_MAX_DIAS_BUSQUEDA = 90


@dataclass
class HorarioEmpleada:
    employee_code: str
    descanso_weekday: int | None = None  # 0=lunes .. 6=domingo
    ciclo_dias_pago: int = 6
    fecha_ultimo_pago: date | None = None
    # {fecha: tipo_evento} — el evento del día le gana al patrón fijo.
    eventos: dict[date, str] = field(default_factory=dict)


# ─── Lógica pura ─────────────────────────────────────────────────────────


def estado_del_dia(horario: HorarioEmpleada, dia: date) -> str:
    """Qué es este día para la empleada: trabajo/descanso/falta/pago."""
    evento = horario.eventos.get(dia)
    if evento == PAGO:
        # El pago se cobra en un día trabajado; se pinta como pago.
        return PAGO
    if evento in (FALTA, DESCANSO, TRABAJO):
        return evento
    if horario.descanso_weekday is not None and dia.weekday() == horario.descanso_weekday:
        return DESCANSO
    return TRABAJO


def es_dia_trabajado(horario: HorarioEmpleada, dia: date) -> bool:
    return estado_del_dia(horario, dia) in (TRABAJO, PAGO)


def dias_trabajados_desde_ultimo_pago(horario: HorarioEmpleada, hoy: date) -> int:
    """Días trabajados DESPUÉS del último pago, hasta hoy inclusive."""
    if horario.fecha_ultimo_pago is None:
        return 0
    dia = horario.fecha_ultimo_pago + timedelta(days=1)
    contados = 0
    while dia <= hoy:
        if es_dia_trabajado(horario, dia):
            contados += 1
        dia += timedelta(days=1)
    return contados


def fecha_proximo_pago(horario: HorarioEmpleada, hoy: date) -> date | None:
    """El día en que se completa el ciclo de días trabajados.

    Camina desde el día siguiente al último pago contando días trabajados
    (los futuros se asumen trabajados salvo descanso fijo o evento ya
    capturado): el día que junta `ciclo_dias_pago` es el día de pago. Una
    falta simplemente no cuenta, así que la fecha se recorre sola.
    """
    if horario.fecha_ultimo_pago is None or horario.ciclo_dias_pago <= 0:
        return None
    dia = horario.fecha_ultimo_pago + timedelta(days=1)
    contados = 0
    for _ in range(_MAX_DIAS_BUSQUEDA):
        if es_dia_trabajado(horario, dia):
            contados += 1
            if contados >= horario.ciclo_dias_pago:
                return dia
        dia += timedelta(days=1)
    return None


def dias_para_pago(horario: HorarioEmpleada, hoy: date) -> int | None:
    """Días trabajados que FALTAN para completar el ciclo (0 = ya toca)."""
    if horario.fecha_ultimo_pago is None or horario.ciclo_dias_pago <= 0:
        return None
    trabajados = dias_trabajados_desde_ultimo_pago(horario, hoy)
    return max(horario.ciclo_dias_pago - trabajados, 0)


def pintar_mes(horario: HorarioEmpleada, year: int, month: int) -> dict[date, str]:
    """{fecha: estado} de todos los días del mes, para pintar el calendario."""
    resultado: dict[date, str] = {}
    dia = date(year, month, 1)
    while dia.month == month:
        resultado[dia] = estado_del_dia(horario, dia)
        dia += timedelta(days=1)
    return resultado


def faltas_en_rango(horario: HorarioEmpleada, desde: date, hasta: date) -> int:
    return sum(
        1 for f, t in horario.eventos.items() if t == FALTA and desde <= f <= hasta
    )


def resumen_empleada(horario: HorarioEmpleada, hoy: date) -> str:
    """Línea humana para el encabezado del calendario."""
    partes: list[str] = []
    if horario.descanso_weekday is not None:
        partes.append(f"Descansas los {WEEKDAY_NAMES[horario.descanso_weekday]}")
    proximo = fecha_proximo_pago(horario, hoy)
    if proximo is not None:
        faltan = dias_para_pago(horario, hoy) or 0
        cuando = "¡hoy!" if proximo <= hoy or faltan == 0 else (
            f"{proximo.strftime('%d/%b')} (te faltan {faltan} día{'s' if faltan != 1 else ''})"
        )
        partes.append(f"Próximo pago: {cuando}")
    return " · ".join(partes) if partes else "Sin horario configurado — pídelo al encargado."


# ─── Acceso a datos ──────────────────────────────────────────────────────


def cargar_horario(session, employee_code: str) -> HorarioEmpleada:
    """Horario + eventos de la empleada (con defaults si aún no existe)."""
    from pos_uniformes.database.models import EmpleadaEvento, EmpleadaHorario

    code = str(employee_code).strip().upper()
    fila = session.get(EmpleadaHorario, code)
    horario = HorarioEmpleada(
        employee_code=code,
        descanso_weekday=fila.descanso_weekday if fila else None,
        ciclo_dias_pago=fila.ciclo_dias_pago if fila else 6,
        fecha_ultimo_pago=fila.fecha_ultimo_pago if fila else None,
    )
    filas = (
        session.query(EmpleadaEvento)
        .filter(EmpleadaEvento.employee_code == code)
        .all()
    )
    for ev in filas:
        horario.eventos[ev.fecha] = ev.tipo
    return horario


def guardar_horario(
    session,
    employee_code: str,
    *,
    descanso_weekday: int | None,
    ciclo_dias_pago: int,
) -> None:
    from pos_uniformes.database.models import EmpleadaHorario

    code = str(employee_code).strip().upper()
    fila = session.get(EmpleadaHorario, code)
    if fila is None:
        fila = EmpleadaHorario(employee_code=code)
        session.add(fila)
    fila.descanso_weekday = descanso_weekday
    fila.ciclo_dias_pago = int(ciclo_dias_pago)
    session.commit()


def marcar_dia(
    session, employee_code: str, fecha: date, tipo: str, *, nota: str | None = None
) -> None:
    """Marca el día (falta/descanso/trabajo); reemplaza la marca previa."""
    quitar_marca(session, employee_code, fecha, commit=False)
    from pos_uniformes.database.models import EmpleadaEvento

    session.add(
        EmpleadaEvento(
            employee_code=str(employee_code).strip().upper(),
            fecha=fecha,
            tipo=tipo,
            nota=nota,
        )
    )
    session.commit()


def quitar_marca(session, employee_code: str, fecha: date, *, commit: bool = True) -> None:
    from pos_uniformes.database.models import EmpleadaEvento

    session.query(EmpleadaEvento).filter(
        EmpleadaEvento.employee_code == str(employee_code).strip().upper(),
        EmpleadaEvento.fecha == fecha,
        EmpleadaEvento.tipo != PAGO,  # el historial de pagos no se pisa al remarcar
    ).delete()
    if commit:
        session.commit()


def registrar_pago(session, employee_code: str, fecha: date) -> None:
    """Anota el pago del día y arranca el siguiente ciclo desde esa fecha."""
    from pos_uniformes.database.models import EmpleadaEvento, EmpleadaHorario

    code = str(employee_code).strip().upper()
    fila = session.get(EmpleadaHorario, code)
    if fila is None:
        fila = EmpleadaHorario(employee_code=code)
        session.add(fila)
    fila.fecha_ultimo_pago = fecha
    ya = (
        session.query(EmpleadaEvento)
        .filter(
            EmpleadaEvento.employee_code == code,
            EmpleadaEvento.fecha == fecha,
            EmpleadaEvento.tipo == PAGO,
        )
        .first()
    )
    if ya is None:
        session.add(EmpleadaEvento(employee_code=code, fecha=fecha, tipo=PAGO))
    session.commit()


def comisiones_desde_ultimo_pago(session, employee_code: str, horario: HorarioEmpleada) -> int:
    """Comisiones acumuladas en la Libreta desde el último pago (para el
    banner "Comisiones desde tu último pago")."""
    from sqlalchemy import func as sa_func

    from pos_uniformes.database.models import LibretaVenta

    query = session.query(sa_func.coalesce(sa_func.sum(LibretaVenta.comisiones), 0)).filter(
        LibretaVenta.employee_code == str(employee_code).strip().upper()
    )
    if horario.fecha_ultimo_pago is not None:
        # El pago cubre hasta ese día completo: cuenta desde el siguiente.
        from datetime import datetime, time, timedelta as _td

        corte = datetime.combine(
            horario.fecha_ultimo_pago + _td(days=1), time.min
        ).astimezone()
        query = query.filter(LibretaVenta.created_at >= corte)
    return int(query.scalar() or 0)


def chips_calendario_mes(session, year: int, month: int, hoy: date) -> dict[date, list[tuple[str, str]]]:
    """Chips del calendario COMPARTIDO (página Calendario del kiosko):
    {fecha: [(tipo, texto)]} con los descansos y pagos de las empleadas.

    Se pintan: descansos (fijos y movidos), pagos ya hechos y el PRÓXIMO
    pago proyectado de cada una. Las faltas NO salen aquí — son del
    calendario privado de la Libreta.
    """
    from pos_uniformes.database.models import Empleada, EmpleadaHorario

    nombres: dict[str, str] = {}
    try:
        for emp in session.query(Empleada).filter(Empleada.activo.is_(True)).all():
            nombres[str(emp.codigo).upper()] = (emp.nombre_completo or emp.codigo).split()[0]
    except Exception:  # noqa: BLE001 — sin nombres, se usa el código
        pass

    resultado: dict[date, list[tuple[str, str]]] = {}

    def _agregar(fecha: date, tipo: str, code: str) -> None:
        if fecha.year == year and fecha.month == month:
            nombre = nombres.get(code, code)
            resultado.setdefault(fecha, []).append((tipo, nombre))

    codigos = [
        fila.employee_code for fila in session.query(EmpleadaHorario).all()
    ]
    for code in codigos:
        horario = cargar_horario(session, code)
        for fecha, estado in pintar_mes(horario, year, month).items():
            if estado == DESCANSO:
                _agregar(fecha, DESCANSO, code)
            elif estado == PAGO:
                _agregar(fecha, PAGO, code)
        proximo = fecha_proximo_pago(horario, hoy)
        if proximo is not None and proximo not in horario.eventos:
            _agregar(proximo, PAGO, code)
    return resultado
