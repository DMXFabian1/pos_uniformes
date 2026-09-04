"""Calendario de empleadas: descansos, faltas, pagos y comisiones del ciclo.

Reglas del negocio (definidas por Daniel):
- Descanso: un día FIJO de la semana por empleada (excepciones por evento).
- Pago: cada 7 días DE CALENDARIO desde el último pago — así cada semana
  cobran el MISMO día. Una falta NO mueve la fecha (se descuenta al pagar);
  queda registrada para el control del dueño.
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

@dataclass
class HorarioEmpleada:
    employee_code: str
    descanso_weekday: int | None = None  # 0=lunes .. 6=domingo
    # Días de CALENDARIO entre pagos (7 = semanal, mismo día cada semana).
    ciclo_dias_pago: int = 7
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
    """Último pago + ciclo de CALENDARIO (7 = mismo día cada semana).

    La falta no mueve la fecha: el pago cae siempre el mismo día de la
    semana y lo faltado se descuenta a la hora de pagar. Si el pago quedó
    atrasado (Daniel no lo ha registrado), se sigue mostrando el vencido.
    """
    if horario.fecha_ultimo_pago is None or horario.ciclo_dias_pago <= 0:
        return None
    return horario.fecha_ultimo_pago + timedelta(days=horario.ciclo_dias_pago)


def dias_para_pago(horario: HorarioEmpleada, hoy: date) -> int | None:
    """Días de calendario que faltan para el próximo pago (0 = ya toca)."""
    proximo = fecha_proximo_pago(horario, hoy)
    if proximo is None:
        return None
    return max((proximo - hoy).days, 0)


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
        ciclo_dias_pago=fila.ciclo_dias_pago if fila else 7,
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


# ─── Autoservicio de descansos (reglas de Daniel, sin negociación) ───────
# 1) Cupo: máximo 1 empleada descansando por día.
# 2) Anticipación: descansos y cambios se piden con 7 días.
# 3) Intercambios: si ambas aceptan con gafete, quedan hechos solos.

ANTICIPACION_DIAS = 7
CUPO_DESCANSOS_POR_DIA = 1


def _semana_de(fecha: date) -> tuple[date, date]:
    lunes = fecha - timedelta(days=fecha.weekday())
    return lunes, lunes + timedelta(days=6)


def descanso_en_semana(horario: HorarioEmpleada, fecha: date) -> date | None:
    """El día que descansa la empleada en la semana de `fecha` (o None)."""
    lunes, domingo = _semana_de(fecha)
    dia = lunes
    while dia <= domingo:
        if estado_del_dia(horario, dia) == DESCANSO:
            return dia
        dia += timedelta(days=1)
    return None


def quienes_descansan(horarios: dict[str, HorarioEmpleada], fecha: date) -> list[str]:
    return [
        code
        for code, h in horarios.items()
        if estado_del_dia(h, fecha) == DESCANSO
    ]


def validar_solicitud_descanso(
    horarios: dict[str, HorarioEmpleada], code: str, fecha: date, hoy: date
) -> tuple[bool, str]:
    """(ok, motivo). Reglas duras — si pasan, se aprueba sin preguntar."""
    code = str(code).strip().upper()
    if (fecha - hoy).days < ANTICIPACION_DIAS:
        return False, (
            f"Los descansos se piden con {ANTICIPACION_DIAS} días de anticipación."
        )
    propio = horarios.get(code)
    if propio is not None and estado_del_dia(propio, fecha) == DESCANSO:
        return False, "Ese día ya es tu descanso."
    ocupantes = [c for c in quienes_descansan(horarios, fecha) if c != code]
    if len(ocupantes) >= CUPO_DESCANSOS_POR_DIA:
        return False, f"Ese día ya descansa {', '.join(ocupantes)}."
    return True, ""


def dias_libres_cercanos(
    horarios: dict[str, HorarioEmpleada],
    code: str,
    hoy: date,
    *,
    cuantos: int = 3,
) -> list[date]:
    """Días que SÍ se pueden pedir, para sugerir en vez de negociar."""
    libres: list[date] = []
    dia = hoy + timedelta(days=ANTICIPACION_DIAS)
    for _ in range(21):
        ok, _motivo = validar_solicitud_descanso(horarios, code, dia, hoy)
        if ok:
            libres.append(dia)
            if len(libres) >= cuantos:
                break
        dia += timedelta(days=1)
    return libres


def aplicar_solicitud_descanso(
    session,
    horarios: dict[str, HorarioEmpleada],
    code: str,
    fecha: date,
    hoy: date,
) -> tuple[bool, str]:
    """Valida y aplica: el descanso de esa semana se MUEVE al día pedido
    (cuota de 1 por semana se cumple sola); si esa semana no tenía, se
    otorga. Devuelve (ok, mensaje para la empleada)."""
    code = str(code).strip().upper()
    ok, motivo = validar_solicitud_descanso(horarios, code, fecha, hoy)
    if not ok:
        return False, motivo
    tope = _valida_cuota_mensual(session, code, hoy)
    if tope is not None:
        return False, tope
    propio = horarios.get(code) or HorarioEmpleada(employee_code=code)
    viejo = descanso_en_semana(propio, fecha)
    if viejo is not None and viejo != fecha:
        marcar_dia(session, code, viejo, TRABAJO, nota="movió su descanso")
    marcar_dia(session, code, fecha, DESCANSO, nota=_NOTA_PEDIDO)
    if viejo is not None and viejo != fecha:
        return True, (
            f"Listo: descansas el {fecha.strftime('%d/%b')} y trabajas el "
            f"{viejo.strftime('%d/%b')} (tu descanso de esa semana se movió)."
        )
    return True, f"Listo: descansas el {fecha.strftime('%d/%b')}."


def validar_intercambio(
    horarios: dict[str, HorarioEmpleada],
    code_a: str,
    fecha_a: date,
    code_b: str,
    fecha_b: date,
    hoy: date,
) -> tuple[bool, str]:
    """A cede su descanso de fecha_a y toma el de B en fecha_b (y viceversa)."""
    code_a = str(code_a).strip().upper()
    code_b = str(code_b).strip().upper()
    if code_a == code_b:
        return False, "El intercambio es entre dos compañeras distintas."
    if fecha_a == fecha_b:
        return False, "Son el mismo día: no hay nada que intercambiar."
    for fecha in (fecha_a, fecha_b):
        if (fecha - hoy).days < ANTICIPACION_DIAS:
            return False, (
                f"Los cambios se piden con {ANTICIPACION_DIAS} días de anticipación."
            )
    ha, hb = horarios.get(code_a), horarios.get(code_b)
    if ha is None or estado_del_dia(ha, fecha_a) != DESCANSO:
        return False, f"El {fecha_a.strftime('%d/%b')} no es descanso de {code_a}."
    if hb is None or estado_del_dia(hb, fecha_b) != DESCANSO:
        return False, f"El {fecha_b.strftime('%d/%b')} no es descanso de {code_b}."
    return True, ""


def aplicar_intercambio(
    session,
    horarios: dict[str, HorarioEmpleada],
    code_a: str,
    fecha_a: date,
    code_b: str,
    fecha_b: date,
    hoy: date,
) -> tuple[bool, str]:
    """Intercambio directo (suma cero: el cupo por día no cambia)."""
    ok, motivo = validar_intercambio(horarios, code_a, fecha_a, code_b, fecha_b, hoy)
    if not ok:
        return False, motivo
    code_a = str(code_a).strip().upper()
    code_b = str(code_b).strip().upper()
    for code in (code_a, code_b):
        tope = _valida_cuota_mensual(session, code, hoy)
        if tope is not None:
            return False, f"{code}: {tope}"
    marcar_dia(session, code_a, fecha_a, TRABAJO, nota=f"intercambio con {code_b}")
    marcar_dia(session, code_a, fecha_b, DESCANSO, nota=f"intercambio con {code_b}")
    marcar_dia(session, code_b, fecha_b, TRABAJO, nota=f"intercambio con {code_a}")
    marcar_dia(session, code_b, fecha_a, DESCANSO, nota=f"intercambio con {code_a}")
    return True, (
        f"Hecho: {code_a} descansa el {fecha_b.strftime('%d/%b')} y "
        f"{code_b} el {fecha_a.strftime('%d/%b')}."
    )


def cargar_horarios_todos(session) -> dict[str, HorarioEmpleada]:
    """Todos los horarios (para validar cupo e intercambios)."""
    from pos_uniformes.database.models import EmpleadaHorario

    return {
        fila.employee_code: cargar_horario(session, fila.employee_code)
        for fila in session.query(EmpleadaHorario).all()
    }


# ─── Encargado y límite mensual de movimientos ───────────────────────────

# Gafete del encargado (el papá de Daniel): puede marcar faltas/descansos
# en el calendario de cualquier empleada, pero NO ve dinero ni registra
# pagos ni cambia horarios. "Si no está en el calendario, no existe."
ENCARGADO_CODE = "ENC-1"

# Cada empleada puede hacer 2 movimientos al mes (pedidos + intercambios
# juntos, para que no se brinque la regla pidiendo en vez de cambiar).
CAMBIOS_POR_MES = 2

_NOTA_PEDIDO = "pedido desde la Libreta"
_NOTA_INTERCAMBIO = "intercambio con "


def cambios_del_mes(session, employee_code: str, hoy: date) -> int:
    """Movimientos de autoservicio hechos este mes (pedidos + intercambios)."""
    from datetime import datetime

    from pos_uniformes.database.models import EmpleadaEvento

    inicio_mes = datetime(hoy.year, hoy.month, 1)
    filas = (
        session.query(EmpleadaEvento)
        .filter(
            EmpleadaEvento.employee_code == str(employee_code).strip().upper(),
            EmpleadaEvento.tipo == DESCANSO,
            EmpleadaEvento.created_at >= inicio_mes,
        )
        .all()
    )
    return sum(
        1
        for f in filas
        if f.nota and (f.nota == _NOTA_PEDIDO or f.nota.startswith(_NOTA_INTERCAMBIO))
    )


def _valida_cuota_mensual(session, employee_code: str, hoy: date) -> str | None:
    usados = cambios_del_mes(session, employee_code, hoy)
    if usados >= CAMBIOS_POR_MES:
        return (
            f"Ya usaste tus {CAMBIOS_POR_MES} cambios de este mes. "
            "El siguiente mes puedes volver a pedir."
        )
    return None
