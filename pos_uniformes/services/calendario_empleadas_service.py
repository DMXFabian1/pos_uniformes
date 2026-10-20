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

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

WEEKDAY_NAMES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

# Estados posibles de un día (para pintar el calendario).
TRABAJO = "trabajo"
DESCANSO = "descanso"
FALTA = "falta"
PAGO = "pago"
#: De vacaciones (módulo vacaciones_service). Pagado, no trabajado, y no es
#: descanso: no cuenta para mover descansos ni para el tope de cambios.
VACACIONES = "vacaciones"

MODO_SEMANA = "semana"     # sueldo fijo, un descanso a la semana
MODO_POR_DIA = "por_dia"   # solo ciertos días; cobra por día trabajado


@dataclass
class HorarioEmpleada:
    employee_code: str
    descanso_weekday: int | None = None  # 0=lunes .. 6=domingo
    # Días de CALENDARIO entre pagos (7 = semanal, mismo día cada semana).
    ciclo_dias_pago: int = 7
    fecha_ultimo_pago: date | None = None
    # {fecha: tipo_evento} — el evento del día le gana al patrón fijo.
    eventos: dict[date, str] = field(default_factory=dict)
    modo_pago: str = MODO_SEMANA
    # Modo por_dia: weekdays que trabaja (p.ej. [5, 6] = sábado y domingo).
    dias_trabajo: list[int] = field(default_factory=list)
    # Días en que se registró un pago. Va aparte de `eventos` porque un día
    # puede tener pago Y otra marca (le pagaron el día que descansó): en un
    # solo dict uno pisaba al otro según el orden en que llegaran de la base.
    pagos: set[date] = field(default_factory=set)

    @property
    def por_dia(self) -> bool:
        return self.modo_pago == MODO_POR_DIA

    @property
    def configurado(self) -> bool:
        """Tiene lo mínimo para calcular pagos y descansos."""
        if self.por_dia:
            return bool(self.dias_trabajo)
        return self.descanso_weekday is not None


def dias_trabajo_texto(horario: HorarioEmpleada) -> str:
    """'sáb, dom' para modo por_dia."""
    cortos = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
    return ", ".join(cortos[d] for d in sorted(set(horario.dias_trabajo)) if 0 <= d <= 6)


# ─── Lógica pura ─────────────────────────────────────────────────────────


def estado_del_dia(horario: HorarioEmpleada, dia: date) -> str:
    """Qué es este día para la empleada: trabajo/descanso/falta/pago."""
    evento = horario.eventos.get(dia)
    if evento == PAGO:
        # El pago se cobra en un día trabajado; se pinta como pago.
        return PAGO
    if evento == VACACIONES:
        return VACACIONES
    if evento in (FALTA, DESCANSO):
        # Faltó o descansó aunque ese día se le haya pagado: el pago no la
        # vuelve día trabajado (ni le quita la falta a la nómina).
        return evento
    if evento == TRABAJO:
        return PAGO if dia in horario.pagos else TRABAJO
    if horario.por_dia:
        return TRABAJO if dia.weekday() in horario.dias_trabajo else DESCANSO
    if horario.descanso_weekday is not None and dia.weekday() == horario.descanso_weekday:
        return DESCANSO
    return TRABAJO


def es_descanso_efectivo(horario: HorarioEmpleada, dia: date) -> bool:
    """¿Ese día descansa, de verdad? Como `estado_del_dia`, salvo que un pago
    registrado en su día de descanso fijo no le quita el descanso (se pinta
    "pago", pero no vino a trabajar). Es lo que se usa para contar los
    descansos de una semana."""
    estado = estado_del_dia(horario, dia)
    if estado == DESCANSO:
        return True
    if estado == PAGO and horario.eventos.get(dia) == PAGO and not horario.por_dia:
        return horario.descanso_weekday is not None and dia.weekday() == horario.descanso_weekday
    return False


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
    if horario.por_dia:
        # Cobra al terminar sus días: el último día de trabajo de la semana
        # (p.ej. domingo si trabaja sáb y dom). Sin último pago: el próximo
        # a partir de hoy. Si ya venció y no se registró, se sigue mostrando.
        if not horario.dias_trabajo:
            return None
        ultimo_wd = max(horario.dias_trabajo)
        dia = (horario.fecha_ultimo_pago + timedelta(days=1)) if horario.fecha_ultimo_pago else hoy
        for _ in range(8):
            if dia.weekday() == ultimo_wd:
                return dia
            dia += timedelta(days=1)
        return None
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
    """Faltas marcadas en el rango, tal cual."""
    return sum(
        1 for f, t in horario.eventos.items() if t == FALTA and desde <= f <= hasta
    )


def dias_extra_en_rango(horario: HorarioEmpleada, desde: date, hasta: date) -> int:
    """Días que trabajó DE MÁS: vino en su descanso fijo sin haber descansado
    otro día de esa semana. Si el descanso se movió (martes descanso, sábado
    trabaja), ese sábado no es de más: solo compensa el martes."""
    if horario.por_dia or horario.descanso_weekday is None:
        return 0
    por_semana: dict[date, list[int]] = defaultdict(lambda: [0, 0])   # [trabajó el fijo, descansó otro día]
    for f, t in horario.eventos.items():
        if not desde <= f <= hasta:
            continue
        semana = _semana_de(f)[0]
        if t == TRABAJO and f.weekday() == horario.descanso_weekday:
            por_semana[semana][0] += 1
        elif t == DESCANSO and f.weekday() != horario.descanso_weekday:
            por_semana[semana][1] += 1
    return sum(max(0, fijo - movidos) for fijo, movidos in por_semana.values())


def faltas_netas_en_rango(horario: HorarioEmpleada, desde: date, hasta: date) -> int:
    """Lo que de verdad se descuenta: faltas menos días trabajados de más.

    Regla de Daniel (2026-09-13): "solo se descuentan faltas cuando laboran
    menos de sus días". Faltó el martes pero vino el sábado (su descanso) =
    trabajó sus 6 días = nada que descontar.
    """
    return max(0, faltas_en_rango(horario, desde, hasta) - dias_extra_en_rango(horario, desde, hasta))


def proximo_descanso(horario: HorarioEmpleada, hoy: date) -> date | None:
    """El siguiente día de descanso a partir de mañana (fijo o movido)."""
    dia = hoy + timedelta(days=1)
    for _ in range(28):
        if estado_del_dia(horario, dia) == DESCANSO:
            return dia
        dia += timedelta(days=1)
    return None


def resumen_empleada(horario: HorarioEmpleada, hoy: date) -> str:
    """Línea humana para el encabezado del calendario y el banner."""
    partes: list[str] = []
    descanso = proximo_descanso(horario, hoy)
    if descanso is not None:
        partes.append(
            "Tu siguiente descanso: "
            f"{WEEKDAY_NAMES[descanso.weekday()]} {descanso.strftime('%d/%b')}"
        )
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
        modo_pago=(getattr(fila, "modo_pago", None) or MODO_SEMANA) if fila else MODO_SEMANA,
        dias_trabajo=[int(d) for d in (getattr(fila, "dias_trabajo", None) or [])] if fila else [],
    )
    filas = (
        session.query(EmpleadaEvento)
        .filter(EmpleadaEvento.employee_code == code)
        .all()
    )
    for ev in filas:
        if ev.tipo == PAGO:
            horario.pagos.add(ev.fecha)
            # El pago solo ocupa el día si no hay otra marca: la marca manda.
            horario.eventos.setdefault(ev.fecha, PAGO)
        else:
            horario.eventos[ev.fecha] = ev.tipo
    return horario


def guardar_horario(
    session,
    employee_code: str,
    *,
    descanso_weekday: int | None,
    ciclo_dias_pago: int,
    modo_pago: str | None = None,
    dias_trabajo: list[int] | None = None,
    fecha_ultimo_pago: date | None = None,
    actualizar_ultimo_pago: bool = False,
) -> None:
    """Guarda el patrón. `modo_pago`/`dias_trabajo` solo cambian si se pasan;
    `fecha_ultimo_pago` solo si `actualizar_ultimo_pago=True` (puede ser None)."""
    from pos_uniformes.database.models import EmpleadaHorario

    code = str(employee_code).strip().upper()
    fila = session.get(EmpleadaHorario, code)
    if fila is None:
        fila = EmpleadaHorario(employee_code=code)
        session.add(fila)
    fila.descanso_weekday = descanso_weekday
    fila.ciclo_dias_pago = int(ciclo_dias_pago)
    if modo_pago is not None:
        if modo_pago not in (MODO_SEMANA, MODO_POR_DIA):
            raise ValueError(f"modo_pago inválido: {modo_pago!r}")
        fila.modo_pago = modo_pago
    if dias_trabajo is not None:
        fila.dias_trabajo = sorted({int(d) for d in dias_trabajo if 0 <= int(d) <= 6})
    if actualizar_ultimo_pago:
        fila.fecha_ultimo_pago = fecha_ultimo_pago
    session.commit()


_NOTA_DESCANSO_MOVIDO = "descanso movido al "


def marcar_dia(
    session, employee_code: str, fecha: date, tipo: str, *, nota: str | None = None,
    commit: bool = True, actor: str | None = None, origen: str = "admin",
) -> None:
    """Marca el día (falta/descanso/trabajo); reemplaza la marca previa.

    Es el camino ADMINISTRATIVO (el dueño, el encargado, Telegram): apunta lo
    que pasó o lo que se decidió, también en días pasados, y queda en la
    bitácora. Lo que piden las empleadas va por `descansos_service`.

    Un descanso en un día que no es el suyo **mueve** el descanso de esa
    semana: el fijo pasa a "trabaja" (Daniel, 2026-09-13: "faltó, pero
    tomamos ese día como descanso" — no es falta, y no descansa dos veces).

    Si el día tenía un evento de una solicitud aprobada, la solicitud se
    revoca primero (ver `quitar_marca`).
    """
    code = str(employee_code).strip().upper()
    if tipo not in (FALTA, DESCANSO, TRABAJO):
        raise ValueError(f"tipo inválido: {tipo!r}")
    antes = cargar_horario(session, code).eventos.get(fecha)
    quitar_marca(session, code, fecha, commit=False, actor=actor, origen=origen, auditar=False)
    from pos_uniformes.database.models import EmpleadaEvento

    session.add(EmpleadaEvento(employee_code=code, fecha=fecha, tipo=tipo, nota=nota))
    movidos: list[date] = []
    if tipo == DESCANSO:
        session.flush()
        for otro in _otros_descansos_fijos_de_la_semana(session, code, fecha):
            movidos.append(otro)
            session.add(EmpleadaEvento(
                employee_code=code, fecha=otro, tipo=TRABAJO,
                nota=f"{_NOTA_DESCANSO_MOVIDO}{fecha.strftime('%d/%m')}",
            ))
    _auditar(
        session, actor=actor, origen=origen, operacion="marcar_dia", code=code,
        antes={"fecha": fecha.isoformat(), "tipo": antes},
        despues={"fecha": fecha.isoformat(), "tipo": tipo,
                 "fijo_movido_a_trabajo": [d.isoformat() for d in movidos]},
        motivo=nota,
    )
    if commit:
        session.commit()
    else:
        session.flush()


def _auditar(session, *, actor, origen, operacion, code, antes=None, despues=None,
             motivo=None, solicitud_id=None) -> None:
    from pos_uniformes.services.auditoria_ausencias_service import registrar

    registrar(
        session, actor=actor, origen=origen, operacion=operacion,
        entidad="empleada_evento", employee_code=code, antes=antes, despues=despues,
        motivo=motivo, solicitud_id=solicitud_id,
    )


def _otros_descansos_fijos_de_la_semana(session, code: str, fecha: date) -> list[date]:
    """Los días de esa semana que son descanso POR PATRÓN (sin evento propio)
    y no son `fecha`. Un descanso explícito de otro día se respeta."""
    horario = cargar_horario(session, code)
    if horario.por_dia:
        return []
    lunes, domingo = _semana_de(fecha)
    dia = lunes
    out: list[date] = []
    while dia <= domingo:
        if dia != fecha and dia not in horario.eventos and estado_del_dia(horario, dia) == DESCANSO:
            out.append(dia)
        dia += timedelta(days=1)
    return out


_NOTA_RECESO = "receso del dueño"


def marcar_receso(
    session, employee_code: str, desde: date, hasta: date, *, actor: str | None = None,
    origen: str = "admin", commit: bool = True,
) -> int:
    """Apunta las vacaciones del dueño: un evento VACACIONES por día, de
    `desde` a `hasta`. Reemplaza el receso anterior si había. Esos días
    `estado_del_dia` no es DESCANSO, así que su día fijo deja de contar en el
    cupo de las muchachas, y el calendario y los pendientes lo dicen.

    Va aparte del módulo de vacaciones (que sigue en construcción): no toca
    expedientes, saldos ni primas. Devuelve cuántos días quedaron."""
    from pos_uniformes.database.models import EmpleadaEvento

    code = str(employee_code).strip().upper()
    if hasta < desde:
        raise ValueError("hasta va después de desde")
    antes = receso_de(session, code)
    quitar_receso(session, code, actor=actor, origen=origen, commit=False, auditar=False)
    dias: list[date] = []
    d = desde
    while d <= hasta:
        quitar_marca(session, code, d, commit=False, actor=actor, origen=origen, auditar=False)
        session.add(EmpleadaEvento(employee_code=code, fecha=d, tipo=VACACIONES, nota=_NOTA_RECESO))
        dias.append(d)
        d += timedelta(days=1)
    _auditar(
        session, actor=actor, origen=origen, operacion="marcar_receso", code=code,
        antes={"desde": antes[0].isoformat(), "hasta": antes[-1].isoformat()} if antes else None,
        despues={"desde": desde.isoformat(), "hasta": hasta.isoformat(), "dias": len(dias)},
    )
    if commit:
        session.commit()
    else:
        session.flush()
    return len(dias)


def receso_de(session, employee_code: str) -> list[date]:
    """Los días apuntados como receso, en orden."""
    from pos_uniformes.database.models import EmpleadaEvento

    code = str(employee_code).strip().upper()
    return sorted(
        f for (f,) in session.query(EmpleadaEvento.fecha).filter(
            EmpleadaEvento.employee_code == code,
            EmpleadaEvento.tipo == VACACIONES,
            EmpleadaEvento.nota == _NOTA_RECESO,
        ).all()
    )


def quitar_receso(
    session, employee_code: str, *, actor: str | None = None, origen: str = "admin",
    commit: bool = True, auditar: bool = True,
) -> int:
    """Borra el receso apuntado (solo los días con la nota del receso)."""
    from pos_uniformes.database.models import EmpleadaEvento

    code = str(employee_code).strip().upper()
    antes = receso_de(session, code)
    n = session.query(EmpleadaEvento).filter(
        EmpleadaEvento.employee_code == code,
        EmpleadaEvento.tipo == VACACIONES,
        EmpleadaEvento.nota == _NOTA_RECESO,
    ).delete()
    if auditar and n:
        _auditar(
            session, actor=actor, origen=origen, operacion="quitar_receso", code=code,
            antes={"desde": antes[0].isoformat(), "hasta": antes[-1].isoformat()}, despues=None,
        )
    if commit:
        session.commit()
    else:
        session.flush()
    return n


def quitar_marca(
    session, employee_code: str, fecha: date, *, commit: bool = True,
    actor: str | None = None, origen: str = "admin", auditar: bool = True,
) -> None:
    """Quita la marca del día (nunca el pago) y regresa el fijo si se había movido.

    Si la marca la puso una solicitud aprobada, no se borra a escondidas: se
    REVOCA la solicitud completa (sus eventos de ese día y el fijo que movió),
    y queda en la bitácora. Así la aprobación nunca apunta a un evento que ya
    no existe."""
    from pos_uniformes.database.models import EmpleadaEvento

    code = str(employee_code).strip().upper()
    ligadas = {
        sid for (sid,) in session.query(EmpleadaEvento.solicitud_id).filter(
            EmpleadaEvento.employee_code == code,
            EmpleadaEvento.fecha == fecha,
            EmpleadaEvento.solicitud_id.isnot(None),
        ).all()
    }
    if ligadas:
        from pos_uniformes.services import descansos_service as ds

        for sid in sorted(ligadas):
            ds.revocar(
                session, sid, quien=actor or "sistema", origen=origen,
                motivo=f"se cambió el {fecha:%d/%m} desde el calendario",
                permitir_periodo_pagado=True,
            )
    vacaciones = {
        vid for (vid,) in session.query(EmpleadaEvento.vacacion_id).filter(
            EmpleadaEvento.employee_code == code,
            EmpleadaEvento.fecha == fecha,
            EmpleadaEvento.vacacion_id.isnot(None),
        ).all()
    }
    if vacaciones:
        from pos_uniformes.services import vacaciones_service as vs

        for vid in sorted(vacaciones):
            vs.revocar_por_calendario(session, vid, quien=actor or "sistema", fecha=fecha)
    antes = cargar_horario(session, code).eventos.get(fecha) if auditar else None
    # Si lo que se quita es un descanso que movió el fijo, el fijo vuelve.
    session.query(EmpleadaEvento).filter(
        EmpleadaEvento.employee_code == code,
        EmpleadaEvento.tipo == TRABAJO,
        EmpleadaEvento.nota == f"{_NOTA_DESCANSO_MOVIDO}{fecha.strftime('%d/%m')}",
        EmpleadaEvento.fecha >= _semana_de(fecha)[0],
        EmpleadaEvento.fecha <= _semana_de(fecha)[1],
    ).delete()
    session.query(EmpleadaEvento).filter(
        EmpleadaEvento.employee_code == code,
        EmpleadaEvento.fecha == fecha,
        EmpleadaEvento.tipo != PAGO,  # el historial de pagos no se pisa al remarcar
    ).delete()
    if auditar and antes not in (None, PAGO):
        _auditar(
            session, actor=actor, origen=origen, operacion="quitar_marca", code=code,
            antes={"fecha": fecha.isoformat(), "tipo": antes}, despues=None,
        )
    if commit:
        session.commit()
    else:
        session.flush()


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
    banner "Comisiones desde tu último pago").

    Cuenta también las ventas privadas: lo que Daniel oculta es el dinero,
    nunca lo que la empleada se ganó."""
    from sqlalchemy import func as sa_func

    from pos_uniformes.database.models import LibretaVenta

    query = session.query(sa_func.coalesce(sa_func.sum(LibretaVenta.comisiones), 0)).filter(
        LibretaVenta.employee_code == str(employee_code).strip().upper()
    )
    if horario.fecha_ultimo_pago is not None:
        query = query.filter(
            LibretaVenta.created_at >= _corte_de_comisiones(session, employee_code, horario)
        )
    return int(query.scalar() or 0)


def _corte_de_comisiones(session, employee_code: str, horario: HorarioEmpleada):
    """Desde qué momento cuentan las comisiones del siguiente pago.

    Lo natural seria "desde el dia siguiente al ultimo pago", y asi estaba. El
    problema: el pago se registra a una HORA. A Cristal se le pagó el 3-oct a
    las 09:13 y siguió vendiendo todo el día; esas 11 comisiones no entraron en
    su pago (no existían todavía) y tampoco en el siguiente (que empieza el
    4-oct). Se perdieron sin que nadie las borrara (Daniel, 2026-10-05).

    Así que el corte es el MOMENTO del último pago, no el final de ese día.
    Las comisiones del salario no cambian: el día del pago se paga completo y
    el ciclo de días sigue empezando al día siguiente; lo que se arregla es que
    las comisiones de esa tarde no caigan en el hueco.

    Si el pago se registró con una fecha distinta al día en que se capturó (un
    pago adelantado o atrasado), no se puede usar su hora: ahí manda el día
    siguiente a la fecha del pago, como antes.
    """
    from datetime import datetime, time, timedelta as _td

    del_dia_siguiente = datetime.combine(
        horario.fecha_ultimo_pago + _td(days=1), time.min
    ).astimezone()

    try:
        from pos_uniformes.database.models import EmpleadaPago

        pago = (
            session.query(EmpleadaPago)
            .filter(EmpleadaPago.employee_code == str(employee_code).strip().upper())
            .order_by(EmpleadaPago.created_at.desc())
            .first()
        )
    except Exception:  # noqa: BLE001 — base sin la tabla todavía
        return del_dia_siguiente

    if pago is None or pago.created_at is None or pago.fecha != horario.fecha_ultimo_pago:
        return del_dia_siguiente
    momento = pago.created_at
    momento = momento.astimezone() if momento.tzinfo else momento.astimezone()
    # El momento de captura, siempre: las comisiones de ese pago se contaron
    # hasta esa hora. Antes se topaba al día siguiente de la fecha del pago, y
    # un pago registrado TARDE (se pagó el domingo, se capturó el lunes a las
    # 17:14 y luego se le corrigió la fecha) volvía a contar las comisiones
    # del lunes en el siguiente pago (2026-10-20).
    return momento


def chips_calendario_mes(session, year: int, month: int, hoy: date) -> dict[date, list[tuple[str, str]]]:
    """Chips del calendario COMPARTIDO (página Calendario del kiosko):
    {fecha: [(tipo, texto)]} con descansos, pagos y faltas de las empleadas.

    Se pintan: descansos (fijos y movidos), pagos ya hechos, el PRÓXIMO pago
    proyectado de cada una y las faltas apuntadas (Daniel las quiso aquí,
    2026-09-09: el encargado apunta y todos ven lo mismo).
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
                # Por días (Naye: solo fines de semana): los días que no le
                # tocan NO son descansos, no ensucian el calendario (Daniel 2026-09-09).
                if horario.por_dia:
                    continue
                _agregar(fecha, DESCANSO, code)
            elif estado == PAGO:
                _agregar(fecha, PAGO, code)
            elif estado == FALTA:
                _agregar(fecha, FALTA, code)
            elif estado == VACACIONES:
                # Se ve con los descansos (está fuera), marcado como vacaciones.
                nombre = nombres.get(code, code)
                if fecha.year == year and fecha.month == month:
                    resultado.setdefault(fecha, []).append((DESCANSO, f"{nombre} (vacaciones)"))
        proximo = fecha_proximo_pago(horario, hoy)
        if proximo is not None and proximo not in horario.eventos:
            _agregar(proximo, PAGO, code)
    return resultado


# ─── Autoservicio de descansos (reglas de Daniel, sin negociación) ───────
# 1) Cupo: máximo 1 empleada descansando por día.
# 2) Anticipación: descansos y cambios se piden con 7 días.
# 3) Intercambios: si ambas aceptan con gafete, quedan hechos solos.
#
# Desde 2026-10-12 la validación sigue aquí (pura, con los horarios que pasa
# quien llama) y la APLICACIÓN la hace descansos_service en una sola
# transacción, ligada a una solicitud y con bitácora. Correcciones mínimas
# autorizadas por Daniel: D2 (el tope cuenta el mes del día que descansa y
# borrar el día no devuelve el cambio), D3 (si la semana ya tiene dos
# descansos no se mueve uno solo) y D4 (intercambio solo en la misma semana).

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
    """Códigos con descanso ese día. Las de modo por_dia no cuentan: un día
    que no les toca no es "descanso" (avisarlo solo mete ruido)."""
    return sorted(
        code
        for code, h in horarios.items()
        if not h.por_dia and estado_del_dia(h, fecha) == DESCANSO
    )


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
    *,
    nombre: str = "",
    origen: str = "calendario",
) -> tuple[bool, str]:
    """Valida y aplica: el descanso de esa semana se MUEVE al día pedido
    (cuota de 1 por semana se cumple sola); si esa semana no tenía, se
    otorga. Devuelve (ok, mensaje para la empleada). Confirma todo junto o
    nada (antes eran dos commits separados)."""
    from pos_uniformes.services import descansos_service as ds

    try:
        s = ds.autoservicio(session, horarios, code, fecha, hoy, nombre=nombre, origen=origen)
        session.commit()
    except ds.NoSePuede as exc:
        session.rollback()
        return False, str(exc)
    except Exception:
        session.rollback()
        raise
    if s.fecha_fijo is not None and s.fecha_fijo != fecha:
        return True, (
            f"Listo: descansas el {fecha.strftime('%d/%b')} y trabajas el "
            f"{s.fecha_fijo.strftime('%d/%b')} (tu descanso de esa semana se movió)."
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
    # D4 (2026-10-12): de semanas distintas, una se quedaba sin descanso una
    # semana y la otra también, en la otra.
    if _semana_de(fecha_a) != _semana_de(fecha_b):
        return False, "Los dos días tienen que ser de la misma semana."
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
    *,
    nombre_a: str = "",
    nombre_b: str = "",
    origen: str = "calendario",
) -> tuple[bool, str]:
    """Intercambio directo (suma cero: el cupo por día no cambia). Las cuatro
    marcas van en una sola transacción: o queda completo o no queda nada."""
    from pos_uniformes.services import descansos_service as ds

    try:
        ds.intercambio_directo(
            session, horarios, code_a, fecha_a, code_b, fecha_b, hoy,
            nombre_a=nombre_a, nombre_b=nombre_b, origen=origen,
        )
        session.commit()
    except ds.NoSePuede as exc:
        session.rollback()
        return False, str(exc)
    except Exception:
        session.rollback()
        raise
    code_a = str(code_a).strip().upper()
    code_b = str(code_b).strip().upper()
    return True, (
        f"Hecho: {code_a} descansa el {fecha_b.strftime('%d/%b')} y "
        f"{code_b} el {fecha_a.strftime('%d/%b')}."
    )


def origen_del_dia(session, employee_code: str, fecha: date) -> str:
    """De dónde sale lo que el calendario pinta ese día, en palabras."""
    from pos_uniformes.database.models import (
        EmpleadaEvento, SolicitudDescanso, SolicitudVacaciones,
    )

    code = str(employee_code).strip().upper()
    horario = cargar_horario(session, code)
    eventos = session.query(EmpleadaEvento).filter(
        EmpleadaEvento.employee_code == code, EmpleadaEvento.fecha == fecha
    ).all()
    partes: list[str] = []
    for ev in eventos:
        if ev.tipo == PAGO:
            partes.append("💵 pago registrado")
            continue
        texto = {VACACIONES: "🏖️ vacaciones", DESCANSO: "🛌 descanso", FALTA: "✗ falta",
                 TRABAJO: "trabaja"}.get(ev.tipo, ev.tipo)
        if ev.vacacion_id:
            sv = session.get(SolicitudVacaciones, ev.vacacion_id)
            texto += f" — solicitud de vacaciones #{ev.vacacion_id}"
            if sv is not None and sv.resuelto_por:
                texto += f", aprobada por {sv.resuelto_por}"
        elif ev.solicitud_id:
            sd = session.get(SolicitudDescanso, ev.solicitud_id)
            if sd is not None:
                como = "intercambio" if sd.tipo == "intercambio" else "cambio de descanso"
                quien = "las reglas del Calendario" if sd.resuelto_por == "REGLAS" else sd.resuelto_por
                texto += f" — {como} #{sd.id}, aprobado por {quien}"
        elif ev.nota:
            texto += f" — {ev.nota}"
        else:
            texto += " — marcado a mano"
        partes.append(texto)
    if not [p for p in partes if not p.startswith("💵")]:
        estado = estado_del_dia(horario, fecha)
        partes.insert(0, "🛌 descanso fijo" if estado == DESCANSO else "día normal de trabajo")
    return f"{fecha:%d/%m}: " + " · ".join(partes)


def cargar_horarios_todos(session) -> dict[str, HorarioEmpleada]:
    """Todos los horarios (para validar cupo e intercambios)."""
    from pos_uniformes.database.models import EmpleadaHorario

    return {
        fila.employee_code: cargar_horario(session, fila.employee_code)
        for fila in session.query(EmpleadaHorario).all()
    }


# ─── Encargado y límite mensual de movimientos ───────────────────────────

# Gafete del encargado (ENC-1): marca faltas/descansos de
# cualquier empleada y, desde 2026-09-08, también hace el corte de caja y
# registra los pagos (con el monto calculado por nomina_service). No cambia
# horarios. "Si no está en el calendario, no existe."
ENCARGADO_CODE = "ENC-1"

# Cada empleada puede hacer 2 movimientos al mes (pedidos + intercambios
# juntos, para que no se brinque la regla pidiendo en vez de cambiar).
CAMBIOS_POR_MES = 2

# Notas con las que el autoservicio marcaba antes del 2026-10-12 (sin
# solicitud ligada). Se siguen contando para el tope de esos eventos viejos.
_NOTA_PEDIDO = "pedido desde la Libreta"
_NOTA_INTERCAMBIO = "intercambio con "


def cambios_del_mes(session, employee_code: str, hoy: date) -> int:
    """Movimientos de autoservicio (pedidos + intercambios) del mes de `hoy`.

    D2 (2026-10-12): cuenta el mes del DÍA que pasa a descansar, no el mes en
    que se pidió, y quitar el día después no devuelve el cambio."""
    from pos_uniformes.services import descansos_service as ds

    return ds.cambios_usados(session, employee_code, (hoy.year, hoy.month))
