"""Descansos que piden las empleadas: el motor de las dos puertas.

Hay dos puertas con LAS MISMAS reglas (Daniel, 2026-10-12: se conserva el
modelo antiguo de descansos):
- Calendario (autoservicio): si las reglas pasan, queda aprobado solo, como
  siempre. Intercambio con el gafete de la compañera, también directo.
- Libreta: ella lo pide y Daniel lo aprueba o rechaza desde Telegram, viendo
  cómo queda la semana.

Reglas (las del autoservicio antiguo, `calendario_empleadas_service`):
- 7 días de anticipación.
- Cupo: nadie más descansando ese día (cuenta cualquier horario, como antes).
- 2 cambios al mes por empleada, pedidos + intercambios.
- El descanso de esa semana se MUEVE al día pedido; si esa semana no tenía,
  se otorga.
Correcciones mínimas autorizadas (2026-10-12):
- D2: el tope cuenta el mes del día que pasa a descansar, y quitar el día
  después no devuelve el cambio. Lo pedido en la Libreta aparta su cambio
  mientras espera respuesta (dos pedidos al mismo tiempo no pasan el tope).
- D3: si esa semana ya tiene dos descansos, no se mueve uno solo (quedaban
  dos): se rechaza para que lo revise Daniel.
- D4: el intercambio es entre días de la misma semana.

Mejoras de integridad (sin cambiar reglas): cada cambio queda como una
solicitud ligada a sus eventos; todo se aplica en una sola transacción;
candado contra pedidos simultáneos; un botón viejo de Telegram no decide
nada; lo que nadie contestó vence; bitácora en `auditoria_ausencias`.

Estados: pedido → aprobado | rechazado | cancelado | vencido;
aprobado → revocado. Ninguna función hace commit (salvo los envoltorios del
autoservicio en calendario_empleadas_service, que confirman al final).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from pos_uniformes.database.models import SolicitudDescanso
from pos_uniformes.services.calendario_empleadas_service import ANTICIPACION_DIAS  # noqa: F401

PEDIDO, APROBADO, RECHAZADO, CANCELADO = "pedido", "aprobado", "rechazado", "cancelado"
VENCIDO, REVOCADO = "vencido", "revocado"
#: Los que gastan uno de los cambios del mes (D2: revocar no lo devuelve).
GASTAN_CAMBIO = (PEDIDO, APROBADO, REVOCADO)
TRANSICIONES = {
    PEDIDO: frozenset({APROBADO, RECHAZADO, CANCELADO, VENCIDO}),
    APROBADO: frozenset({REVOCADO}),
}

CAMBIO, INTERCAMBIO = "cambio", "intercambio"

#: Quién resuelve lo que aprueban las reglas del autoservicio.
REGLAS = "REGLAS"

#: Hasta cuántos días adelante deja escoger la Libreta (solo su calendario).
DIAS_MAXIMO_ADELANTE = 60
#: Recordatorios a Daniel de lo que sigue sin contestar.
HORAS_PRIMER_RECORDATORIO = 24
HORAS_ENTRE_RECORDATORIOS = 24

#: Más de esto fuera el mismo día y la tienda se queda corta (solo el aviso).
CUANTAS_FUERA_INCOMODA = 2
#: Semanas atrás que se miran para decir si ese día de la semana es movido.
SEMANAS_DE_REFERENCIA = 4

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre")

#: Llave del candado de Postgres que pone en fila las operaciones de descansos.
_CANDADO = 734_002_611


class NoSePuede(Exception):
    """Algo impide la solicitud, con un mensaje que se le puede enseñar a ella."""


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _code(valor) -> str:
    return str(valor or "").strip().upper()


def _dd(d: date) -> str:
    return f"{_DIAS[d.weekday()]} {d:%d/%m}"


def _semana(fecha: date) -> tuple[date, date]:
    lunes = fecha - timedelta(days=fecha.weekday())
    return lunes, lunes + timedelta(days=6)


def _bloquear(session: Session) -> None:
    """Pone en fila a quien quiera mover descansos hasta el commit."""
    try:
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CANDADO})
    except Exception:  # noqa: BLE001 — sin candado se valida igual
        pass


def _auditar(session, s: SolicitudDescanso, operacion: str, *, quien, origen,
             antes=None, despues=None, motivo=None) -> None:
    from pos_uniformes.services.auditoria_ausencias_service import registrar

    registrar(
        session, actor=quien, origen=origen or "admin", operacion=operacion,
        entidad="solicitud_descanso", entidad_id=s.id, solicitud_id=s.id,
        employee_code=s.employee_code, antes=antes, despues=despues, motivo=motivo,
    )


def _transicion(session, s: SolicitudDescanso, nuevo: str, *, quien, origen,
                motivo=None, despues=None) -> None:
    if nuevo not in TRANSICIONES.get(s.estado, ()):
        raise NoSePuede(f"Esa solicitud ya está {s.estado}.")
    antes = s.estado
    s.estado = nuevo
    if nuevo != REVOCADO:
        s.resuelto_at = _ahora()
        if quien:
            s.resuelto_por = _code(quien)
    session.add(s)
    session.flush()
    _auditar(session, s, nuevo, quien=quien, origen=origen,
             antes={"estado": antes}, despues={"estado": nuevo, **(despues or {})},
             motivo=motivo)


# ── La semana como está ──────────────────────────────────────────────────────

def _horarios_frescos(session, horarios: dict | None = None) -> dict:
    """Lo que dice la base manda; lo que pasó quien llama llena huecos (las
    pruebas y pantallas viejas pasan horarios armados a mano)."""
    from pos_uniformes.services.calendario_empleadas_service import cargar_horarios_todos

    base = dict(horarios or {})
    try:
        base.update(cargar_horarios_todos(session))
    except Exception:  # noqa: BLE001
        pass
    return base


def _horario(horarios: dict, code: str):
    from pos_uniformes.services.calendario_empleadas_service import HorarioEmpleada

    return horarios.get(code) or HorarioEmpleada(employee_code=code)


def _descansos_de_la_semana(horario, fecha: date) -> list[date]:
    from pos_uniformes.services.calendario_empleadas_service import es_descanso_efectivo

    lunes, _ = _semana(fecha)
    return [
        lunes + timedelta(days=i) for i in range(7)
        if es_descanso_efectivo(horario, lunes + timedelta(days=i))
    ]


def _el_que_se_mueve(horario, fecha: date) -> date | None:
    """El descanso de esa semana que pasa a trabajo (None = esa semana no
    tenía y se otorga, como siempre). D3: con dos, se rechaza."""
    if horario.por_dia:
        return None
    otros = [d for d in _descansos_de_la_semana(horario, fecha) if d != fecha]
    if len(otros) > 1:
        raise NoSePuede(
            f"Esa semana ya tienes {len(otros)} descansos apuntados. "
            "Pídeselo a Daniel en persona para que la revise."
        )
    return otros[0] if otros else None


def cambios_usados(session, employee_code: str, mes: tuple[int, int], *,
                   excluir_id: int | None = None) -> int:
    """Cambios del mes (D2): solicitudes que gastan cambio cuyo NUEVO día de
    descanso cae en ese mes, como quien pide o como compañera de intercambio,
    más los eventos del autoservicio de antes (sin solicitud ligada)."""
    from calendar import monthrange

    from pos_uniformes.database.models import EmpleadaEvento
    from pos_uniformes.services.calendario_empleadas_service import (
        _NOTA_INTERCAMBIO, _NOTA_PEDIDO, DESCANSO,
    )

    code = _code(employee_code)
    inicio = date(mes[0], mes[1], 1)
    fin = date(mes[0], mes[1], monthrange(*mes)[1])
    q = select(SolicitudDescanso).where(
        SolicitudDescanso.estado.in_(GASTAN_CAMBIO),
        or_(
            (SolicitudDescanso.employee_code == code)
            & SolicitudDescanso.fecha.between(inicio, fin),
            (SolicitudDescanso.companera_code == code)
            & SolicitudDescanso.fecha_companera.between(inicio, fin),
        ),
    )
    if excluir_id is not None:
        q = q.where(SolicitudDescanso.id != excluir_id)
    nuevos = len(session.scalars(q).all())
    viejos = session.query(EmpleadaEvento).filter(
        EmpleadaEvento.employee_code == code,
        EmpleadaEvento.tipo == DESCANSO,
        EmpleadaEvento.solicitud_id.is_(None),
        EmpleadaEvento.fecha.between(inicio, fin),
        or_(EmpleadaEvento.nota == _NOTA_PEDIDO, EmpleadaEvento.nota.like(f"{_NOTA_INTERCAMBIO}%")),
    ).count()
    return nuevos + viejos


def _revisar_tope(session, code: str, dia: date, *, excluir_id=None, prefijo="") -> None:
    from pos_uniformes.services.calendario_empleadas_service import CAMBIOS_POR_MES

    if cambios_usados(session, code, (dia.year, dia.month), excluir_id=excluir_id) >= CAMBIOS_POR_MES:
        raise NoSePuede(
            f"{prefijo}Ya usaste tus {CAMBIOS_POR_MES} cambios de {_MESES[dia.month - 1]}. "
            "El siguiente mes puedes volver a pedir."
        )


def _no_en_vacaciones(horario, dias) -> None:
    from pos_uniformes.services.calendario_empleadas_service import VACACIONES, estado_del_dia

    for d in dias:
        if estado_del_dia(horario, d) == VACACIONES:
            raise NoSePuede(f"El {_dd(d)} está de vacaciones.")


def validar_cambio(session, horarios: dict, code: str, fecha: date, hoy: date, *,
                   excluir_id: int | None = None, con_anticipacion: bool = True) -> date | None:
    """Las reglas del autoservicio, iguales para el Calendario y la Libreta.
    Devuelve el día que pasaría a trabajo (o None si se otorga)."""
    from pos_uniformes.services.calendario_empleadas_service import (
        CUPO_DESCANSOS_POR_DIA, DESCANSO, estado_del_dia, quienes_descansan,
        validar_solicitud_descanso,
    )

    code = _code(code)
    if fecha < hoy:
        raise NoSePuede("Ese día ya pasó.")
    if con_anticipacion:
        ok, motivo = validar_solicitud_descanso(horarios, code, fecha, hoy)
        if not ok:
            raise NoSePuede(motivo)
    else:
        # Al aprobar lo pedido en la Libreta: la anticipación se midió al
        # pedirlo; cupo y su propio descanso se vuelven a mirar.
        propio = horarios.get(code)
        if propio is not None and estado_del_dia(propio, fecha) == DESCANSO:
            raise NoSePuede("Ese día ya es su descanso.")
        ocupantes = [c for c in quienes_descansan(horarios, fecha) if c != code]
        if len(ocupantes) >= CUPO_DESCANSOS_POR_DIA:
            raise NoSePuede(f"Ese día ya descansa {', '.join(ocupantes)}.")
    horario = _horario(horarios, code)
    _no_en_vacaciones(horario, [fecha])
    _revisar_tope(session, code, fecha, excluir_id=excluir_id)
    return _el_que_se_mueve(horario, fecha)


# ── Aplicar ──────────────────────────────────────────────────────────────────

def _poner(session, code: str, dia: date, tipo: str, solicitud_id: int, nota: str) -> dict:
    """Deja `tipo` como LA marca del día, ligada a la solicitud (el pago nunca
    se toca)."""
    from pos_uniformes.database.models import EmpleadaEvento
    from pos_uniformes.services.calendario_empleadas_service import PAGO

    previas = session.query(EmpleadaEvento).filter(
        EmpleadaEvento.employee_code == code,
        EmpleadaEvento.fecha == dia,
        EmpleadaEvento.tipo != PAGO,
    ).all()
    antes = [p.tipo for p in previas]
    for p in previas:
        session.delete(p)
    session.flush()
    session.add(EmpleadaEvento(
        employee_code=code, fecha=dia, tipo=tipo, nota=nota[:200], solicitud_id=solicitud_id,
    ))
    session.flush()
    return {"code": code, "fecha": dia.isoformat(), "antes": antes, "despues": tipo}


def _aplicar_cambio(session, s: SolicitudDescanso, fijo: date | None, nota: str) -> list[dict]:
    from pos_uniformes.services.calendario_empleadas_service import (
        _NOTA_PEDIDO, DESCANSO, TRABAJO,
    )

    code = _code(s.employee_code)
    cambios = [_poner(session, code, s.fecha, DESCANSO, s.id, nota or _NOTA_PEDIDO)]
    if fijo is not None:
        cambios.append(_poner(session, code, fijo, TRABAJO, s.id, "movió su descanso"))
    s.fecha_fijo = fijo
    return cambios


def _candado_final(session, codes, fecha: date, antes: dict[str, int]) -> None:
    """Después de aplicar, nadie puede quedar con más descansos esa semana de
    los que tenía (o uno, si no tenía): así se evita el doble descanso."""
    horarios = _horarios_frescos(session)
    for code in codes:
        h = _horario(horarios, code)
        if h.por_dia:
            continue
        if len(_descansos_de_la_semana(h, fecha)) > max(1, antes.get(code, 0)):
            raise NoSePuede("Aplicarlo dejaría un descanso de más en la semana; que lo revise Daniel.")


def autoservicio(session: Session, horarios: dict, code: str, fecha: date, hoy: date, *,
                 nombre: str = "", origen: str = "calendario") -> SolicitudDescanso:
    """Puerta del Calendario: si las reglas pasan, queda aprobado solo (como
    siempre). Queda registrado como solicitud aprobada por las reglas."""
    from pos_uniformes.services.calendario_empleadas_service import _NOTA_PEDIDO

    code = _code(code)
    _bloquear(session)
    horarios = _horarios_frescos(session, horarios)
    fijo = validar_cambio(session, horarios, code, fecha, hoy)
    antes = {code: len(_descansos_de_la_semana(_horario(horarios, code), fecha))}
    s = SolicitudDescanso(
        employee_code=code, employee_name=str(nombre or ""), tipo=CAMBIO, fecha=fecha,
        fecha_fijo=fijo, motivo="autoservicio del Calendario", estado=PEDIDO,
        origen=origen, recordatorios=0, avisada_at=_ahora(),
    )
    session.add(s)
    session.flush()
    _auditar(session, s, "pedir", quien=code, origen=origen,
             despues={"fecha": fecha.isoformat()})
    cambios = _aplicar_cambio(session, s, fijo, _NOTA_PEDIDO)
    _candado_final(session, [code], fecha, antes)
    _transicion(session, s, APROBADO, quien=REGLAS, origen=origen, despues={"eventos": cambios})
    return s


def intercambio_directo(session: Session, horarios: dict, code_a: str, fecha_a: date,
                        code_b: str, fecha_b: date, hoy: date, *, nombre_a: str = "",
                        nombre_b: str = "", origen: str = "calendario") -> SolicitudDescanso:
    """A da su descanso de `fecha_a` y toma el de B en `fecha_b`; B aceptó con
    su gafete. Directo, como siempre, pero las cuatro marcas van juntas."""
    from pos_uniformes.services.calendario_empleadas_service import (
        DESCANSO, TRABAJO, validar_intercambio,
    )

    a, b = _code(code_a), _code(code_b)
    _bloquear(session)
    horarios = _horarios_frescos(session, horarios)
    ok, motivo = validar_intercambio(horarios, a, fecha_a, b, fecha_b, hoy)
    if not ok:
        raise NoSePuede(motivo)
    _no_en_vacaciones(_horario(horarios, a), [fecha_b])
    _no_en_vacaciones(_horario(horarios, b), [fecha_a])
    _revisar_tope(session, a, fecha_b, prefijo=f"{a}: ")
    _revisar_tope(session, b, fecha_a, prefijo=f"{b}: ")
    antes = {c: len(_descansos_de_la_semana(_horario(horarios, c), fecha_a)) for c in (a, b)}
    s = SolicitudDescanso(
        employee_code=a, employee_name=str(nombre_a or ""), tipo=INTERCAMBIO,
        fecha=fecha_b, fecha_fijo=fecha_a, companera_code=b,
        companera_name=str(nombre_b or ""), fecha_companera=fecha_a,
        companera_acepto_at=_ahora(), motivo=f"intercambio con {b}", estado=PEDIDO,
        origen=origen, recordatorios=0, avisada_at=_ahora(), companera_avisada_at=_ahora(),
    )
    session.add(s)
    session.flush()
    _auditar(session, s, "pedir_intercambio", quien=a, origen=origen,
             despues={"a": a, "a_descansa": fecha_b.isoformat(),
                      "b": b, "b_descansa": fecha_a.isoformat()})
    cambios = [
        _poner(session, a, fecha_a, TRABAJO, s.id, f"intercambio con {b}"),
        _poner(session, a, fecha_b, DESCANSO, s.id, f"intercambio con {b}"),
        _poner(session, b, fecha_b, TRABAJO, s.id, f"intercambio con {a}"),
        _poner(session, b, fecha_a, DESCANSO, s.id, f"intercambio con {a}"),
    ]
    _candado_final(session, [a, b], fecha_a, antes)
    _transicion(session, s, APROBADO, quien=REGLAS, origen=origen, despues={"eventos": cambios})
    return s


# ── La Libreta: pedir y que Daniel conteste ──────────────────────────────────

def pedir(
    session: Session, *, employee_code: str, nombre: str, fecha: date, motivo: str,
    hoy: date | None = None, origen: str = "kiosko",
) -> SolicitudDescanso:
    """Ella lo pide desde la Libreta, con las reglas del Calendario. Queda
    esperando a Daniel; no toca el calendario hasta que él aprueba."""
    hoy = hoy or date.today()
    code = _code(employee_code)
    _bloquear(session)
    vencer_pendientes(session, hoy=hoy)
    motivo = (motivo or "").strip()
    if not motivo:
        raise NoSePuede("Escribe para qué lo necesitas: sin motivo no se puede autorizar.")
    if pendiente_de(session, code, fecha, hoy=hoy) is not None:
        raise NoSePuede("Ya pediste ese día y está esperando respuesta.")
    if _ya_aprobado(session, code, fecha):
        raise NoSePuede("Ese día ya te lo autorizaron.")
    horarios = _horarios_frescos(session)
    fijo = validar_cambio(session, horarios, code, fecha, hoy)
    solicitud = SolicitudDescanso(
        employee_code=code, employee_name=str(nombre or ""), tipo=CAMBIO,
        fecha=fecha, fecha_fijo=fijo, motivo=motivo[:200], estado=PEDIDO,
        origen=origen, recordatorios=0,
    )
    session.add(solicitud)
    session.flush()
    _auditar(session, solicitud, "pedir", quien=code, origen=origen,
             despues={"fecha": fecha.isoformat(),
                      "fecha_fijo": fijo.isoformat() if fijo else None})
    return solicitud


def _ya_aprobado(session: Session, code: str, fecha: date) -> bool:
    return session.scalars(
        select(SolicitudDescanso).where(
            SolicitudDescanso.employee_code == code,
            SolicitudDescanso.fecha == fecha,
            SolicitudDescanso.estado == APROBADO,
        )
    ).first() is not None


def pendiente_de(session: Session, employee_code: str, fecha: date | None = None,
                 *, hoy: date | None = None):
    """La solicitud sin responder de esa persona (de un día, o la más próxima).

    Solo las de hoy en adelante: una que nadie contestó y cuyo día ya pasó no
    puede seguir escondiendo el botón de pedir (auditoría 2026-10-12)."""
    hoy = hoy or date.today()
    code = _code(employee_code)
    stmt = select(SolicitudDescanso).where(
        SolicitudDescanso.employee_code == code,
        SolicitudDescanso.estado == PEDIDO,
        SolicitudDescanso.fecha >= hoy,
    )
    if fecha is not None:
        stmt = stmt.where(SolicitudDescanso.fecha == fecha)
    return session.scalars(stmt.order_by(SolicitudDescanso.fecha)).first()


def pendientes(session: Session, *, hoy: date | None = None) -> list[SolicitudDescanso]:
    """Todas las que esperan respuesta, la más próxima primero (sin las de días
    que ya pasaron: esas las cierra la tarea del bot como vencidas)."""
    hoy = hoy or date.today()
    return list(session.scalars(
        select(SolicitudDescanso)
        .where(SolicitudDescanso.estado == PEDIDO, SolicitudDescanso.fecha >= hoy)
        .order_by(SolicitudDescanso.fecha, SolicitudDescanso.id)
    ).all())


def sin_responder_que_ya_pasaron(session: Session, *, hoy: date | None = None) -> list[SolicitudDescanso]:
    """Las que se quedaron sin respuesta hasta que el día pasó."""
    hoy = hoy or date.today()
    return list(session.scalars(
        select(SolicitudDescanso)
        .where(or_(
            SolicitudDescanso.estado == VENCIDO,
            (SolicitudDescanso.estado == PEDIDO) & (SolicitudDescanso.fecha < hoy),
        ))
        .order_by(SolicitudDescanso.fecha)
    ).all())


def vencer_pendientes(session: Session, *, hoy: date | None = None,
                      origen: str = "sistema") -> list[SolicitudDescanso]:
    """Cierra como vencidas las que nadie contestó y cuyo día ya pasó: liberan
    su cambio del mes y dejan de bloquearla."""
    hoy = hoy or date.today()
    viejas = list(session.scalars(
        select(SolicitudDescanso).where(
            SolicitudDescanso.estado == PEDIDO, SolicitudDescanso.fecha < hoy,
        )
    ).all())
    for s in viejas:
        _transicion(session, s, VENCIDO, quien=None, origen=origen,
                    motivo="nadie la contestó antes del día")
    return viejas


def _viva(session: Session, solicitud_id: int) -> SolicitudDescanso:
    solicitud = session.get(SolicitudDescanso, int(solicitud_id))
    if solicitud is None:
        raise NoSePuede("Esa solicitud ya no existe.")
    if solicitud.estado != PEDIDO:
        raise NoSePuede(f"Esa solicitud ya está {solicitud.estado}.")
    return solicitud


def aprobar(session: Session, solicitud_id: int, *, quien: str, respuesta: str = "",
            hoy: date | None = None, origen: str = "telegram") -> SolicitudDescanso:
    """Daniel le da el día (lo pedido en la Libreta). Se vuelven a mirar cupo,
    tope y la semana como está HOY, y se aplica completo o nada. Un botón
    viejo encuentra la solicitud ya resuelta y no hace nada."""
    hoy = hoy or date.today()
    _bloquear(session)
    s = _viva(session, solicitud_id)
    if s.fecha < hoy:
        raise NoSePuede("Ese día ya pasó: la solicitud se cierra sola como vencida.")
    code = _code(s.employee_code)
    horarios = _horarios_frescos(session)
    fijo = validar_cambio(session, horarios, code, s.fecha, hoy, excluir_id=s.id,
                          con_anticipacion=False)
    antes = {code: len(_descansos_de_la_semana(_horario(horarios, code), s.fecha))}
    cambios = _aplicar_cambio(session, s, fijo, f"Lo pidió ella: {s.motivo}")
    _candado_final(session, [code], s.fecha, antes)
    s.respuesta = (respuesta or "").strip()[:200] or None
    _transicion(session, s, APROBADO, quien=quien, origen=origen, despues={"eventos": cambios})
    return s


def rechazar(session: Session, solicitud_id: int, *, quien: str, respuesta: str = "",
             origen: str = "telegram") -> SolicitudDescanso:
    """No se le da el día. Nada se escribe en el calendario."""
    s = _viva(session, solicitud_id)
    s.respuesta = (respuesta or "").strip()[:200] or None
    _transicion(session, s, RECHAZADO, quien=quien, origen=origen, motivo=s.respuesta)
    return s


def cancelar(session: Session, solicitud_id: int, *, quien: str, origen: str = "kiosko") -> SolicitudDescanso:
    """Ella se arrepiente antes de que le contesten."""
    s = _viva(session, solicitud_id)
    if _code(quien) != _code(s.employee_code):
        raise NoSePuede("Solo quien la pidió puede cancelarla.")
    _transicion(session, s, CANCELADO, quien=quien, origen=origen)
    return s


def revocar(session: Session, solicitud_id: int, *, quien: str, motivo: str,
            origen: str = "admin", permitir_periodo_pagado: bool = False) -> SolicitudDescanso:
    """Deshace una aprobación: quita sus eventos y la deja `revocado` (la
    solicitud y la bitácora se quedan). D2: el cambio del mes NO se devuelve."""
    from pos_uniformes.database.models import EmpleadaEvento
    from pos_uniformes.services.calendario_empleadas_service import cargar_horario

    motivo = (motivo or "").strip()
    if not motivo:
        raise NoSePuede("Para revocar hace falta el motivo.")
    s = session.get(SolicitudDescanso, int(solicitud_id))
    if s is None:
        raise NoSePuede("Esa solicitud ya no existe.")
    if s.estado != APROBADO:
        raise NoSePuede(f"Esa solicitud ya está {s.estado}.")
    eventos = session.query(EmpleadaEvento).filter(EmpleadaEvento.solicitud_id == s.id).all()
    if not permitir_periodo_pagado:
        for ev in eventos:
            h = cargar_horario(session, ev.employee_code)
            if h.fecha_ultimo_pago is not None and ev.fecha <= h.fecha_ultimo_pago:
                raise NoSePuede(
                    f"El {_dd(ev.fecha)} ya entró en un pago. Corrígelo desde el calendario."
                )
    quitados = [
        {"code": ev.employee_code, "fecha": ev.fecha.isoformat(), "tipo": ev.tipo}
        for ev in eventos
    ]
    for ev in eventos:
        session.delete(ev)
    session.flush()
    _transicion(session, s, REVOCADO, quien=quien, origen=origen, motivo=motivo,
                despues={"eventos_quitados": quitados})
    return s


# ── Lo que ella ve de vuelta (Libreta) ───────────────────────────────────────

_RESUELTOS = (APROBADO, RECHAZADO, VENCIDO, REVOCADO)


def respuestas_sin_ver(session: Session, employee_code: str) -> list[SolicitudDescanso]:
    """Lo que Daniel (o el reloj) ya decidió y ella todavía no ha visto. Lo del
    autoservicio nace visto: ella ya vio el «Listo» en pantalla."""
    code = _code(employee_code)
    return list(session.scalars(
        select(SolicitudDescanso).where(
            SolicitudDescanso.estado.in_(_RESUELTOS),
            or_(
                (SolicitudDescanso.employee_code == code) & SolicitudDescanso.avisada_at.is_(None),
                (SolicitudDescanso.companera_code == code)
                & SolicitudDescanso.companera_avisada_at.is_(None),
            ),
        ).order_by(SolicitudDescanso.id)
    ).all())


def marcar_vista(session: Session, solicitud_id: int, employee_code: str) -> None:
    s = session.get(SolicitudDescanso, int(solicitud_id))
    if s is None:
        return
    code = _code(employee_code)
    if code == _code(s.employee_code) and s.avisada_at is None:
        s.avisada_at = _ahora()
    elif code == _code(s.companera_code) and s.companera_avisada_at is None:
        s.companera_avisada_at = _ahora()
    session.flush()


def texto_de_respuesta(s: SolicitudDescanso, employee_code: str) -> str:
    """Lo que se le enseña a ella en la Libreta."""
    soy_companera = _code(employee_code) == _code(s.companera_code)
    mi_dia = s.fecha_companera if soy_companera else s.fecha
    mi_otro = s.fecha if soy_companera else s.fecha_fijo
    que = "el cambio de descanso" if s.tipo == INTERCAMBIO else "tu descanso"
    if s.estado == APROBADO:
        texto = f"✅ Daniel aprobó {que}: descansas el {_dd(mi_dia)}"
        if mi_otro:
            texto += f" y trabajas el {_dd(mi_otro)}"
        texto += "."
    elif s.estado == RECHAZADO:
        texto = f"✖️ Daniel no aprobó {que} del {_dd(mi_dia)}."
    elif s.estado == VENCIDO:
        texto = (f"⌛ Tu solicitud del {_dd(mi_dia)} se quedó sin respuesta y ya venció. "
                 "Tu calendario no cambió.")
    else:  # revocado
        texto = f"↩️ Se deshizo {que} del {_dd(mi_dia)}. Tu calendario volvió a como estaba."
    if s.respuesta:
        texto += f"\n«{s.respuesta}»"
    return texto


# ── Recordatorios (los corre el bot en cada vuelta) ──────────────────────────

def tarea_periodica(session: Session, *, ahora: datetime | None = None) -> list[tuple[str, str]]:
    """Cierra las vencidas y arma los recordatorios que tocan; sin commit (lo
    confirma quien encola, así un aviso que no entró se vuelve a intentar)."""
    from pos_uniformes.services import telegram_descansos_service as dsc

    ahora = ahora or _ahora()
    hoy = ahora.astimezone().date()
    avisos: list[tuple[str, str]] = []
    vencidas = vencer_pendientes(session, hoy=hoy)
    if vencidas:
        quienes = ", ".join(sorted({(s.employee_name or s.employee_code).split()[0] for s in vencidas}))
        avisos.append((
            f"⌛ Se vencieron {len(vencidas)} días de descanso sin respuesta ({quienes}). "
            "No se aplicó nada; a ellas se les avisa en la Libreta.", "",
        ))
    for s in pendientes(session, hoy=hoy):
        ultimo = s.ultimo_recordatorio_at or s.created_at
        if ultimo is None:
            continue
        if ultimo.tzinfo is None:
            ultimo = ultimo.replace(tzinfo=timezone.utc)
        espera = HORAS_ENTRE_RECORDATORIOS if s.ultimo_recordatorio_at else HORAS_PRIMER_RECORDATORIO
        if ahora - ultimo < timedelta(hours=espera):
            continue
        s.ultimo_recordatorio_at = ahora
        s.recordatorios = int(s.recordatorios or 0) + 1
        session.flush()
        avisos.append((
            "⏰ Sigue sin respuesta:\n" + dsc.aviso_de_solicitud(s, hoy=hoy),
            dsc.botones_de(s),
        ))
    return avisos


# ── Lo que hace falta para decidir ───────────────────────────────────────────

@dataclass(frozen=True)
class DiaDeLaSemana:
    fecha: date
    nombre: str
    trabajan: list[str] = field(default_factory=list)
    descansan: list[str] = field(default_factory=list)
    es_el_pedido: bool = False


@dataclass(frozen=True)
class Contexto:
    """Lo que Daniel necesita ver antes de apretar un botón."""

    fecha: date
    nombre_dia: str
    quien_mas_descansa: list[str] = field(default_factory=list)
    trabajan_ese_dia: list[str] = field(default_factory=list)
    semana: list[DiaDeLaSemana] = field(default_factory=list)
    #: Venta promedio de ese mismo día de la semana en las semanas anteriores.
    venta_tipica: Decimal | None = None
    venta_tipica_de_cuantos: int = 0
    #: Si ese día es el más movido de la semana (según esas mismas semanas).
    es_el_dia_mas_movido: bool = False
    tiene_pago: bool = False
    tiene_conteo: list[str] = field(default_factory=list)

    @property
    def quedaria_corta(self) -> bool:
        return len(self.quien_mas_descansa) + 1 > CUANTAS_FUERA_INCOMODA


def _pila(nombre: str, code: str) -> str:
    texto = str(nombre or code or "").strip()
    return texto.split()[0] if texto else str(code)


def contexto_de(session: Session, solicitud: SolicitudDescanso) -> Contexto:
    """Arma el panorama del día pedido. Cada pieza es defensiva: si una no se
    puede calcular, el resto del aviso sale igual — un dato que falta no puede
    impedir que Daniel conteste."""
    from pos_uniformes.services.calendario_empleadas_service import (
        DESCANSO,
        cargar_horario,
        estado_del_dia,
    )
    from pos_uniformes.services.nomina_service import QUIEN_PUEDE_PAGAR

    fecha = solicitud.fecha
    quien_pide = _code(solicitud.employee_code)

    from pos_uniformes.database.models import Empleada

    try:
        empleadas = [
            e for e in session.query(Empleada).filter(Empleada.activo.is_(True))
            .order_by(Empleada.nombre_completo).all()
            if _code(e.codigo) not in QUIEN_PUEDE_PAGAR
        ]
    except Exception:  # noqa: BLE001
        empleadas = []

    horarios = {}
    for e in empleadas:
        try:
            horarios[_code(e.codigo)] = cargar_horario(session, e.codigo)
        except Exception:  # noqa: BLE001
            pass

    # También cuentan los descansos que YA se autorizaron para ese día.
    aprobados_ese_dia = {
        _code(s.employee_code)
        for s in session.scalars(
            select(SolicitudDescanso).where(
                SolicitudDescanso.fecha == fecha, SolicitudDescanso.estado == APROBADO
            )
        ).all()
    }

    # La semana se pinta COMO QUEDARÍA si se aprueba, que es lo que se le
    # prometió a Daniel. Para la que pide eso significa dos cambios: descansa
    # el día que pidió, y su descanso fijo de esa semana pasa a trabajo. Sin
    # esto el panorama decía "descansa —" en el día que se está decidiendo y la
    # seguía poniendo libre su domingo: justo al contrario de lo que pasaría.
    se_moveria = set()
    horario_pide = horarios.get(quien_pide)
    if getattr(solicitud, "fecha_fijo", None) is not None:
        se_moveria = {solicitud.fecha_fijo}
    elif horario_pide is not None:
        try:
            from pos_uniformes.services.calendario_empleadas_service import (
                _otros_descansos_fijos_de_la_semana,
            )

            se_moveria = set(_otros_descansos_fijos_de_la_semana(session, quien_pide, fecha))
        except Exception:  # noqa: BLE001 — sin esto se pinta sin mover nada
            se_moveria = set()

    def _descansa(code: str, dia: date) -> bool:
        h = horarios.get(code)
        if h is None:
            return False
        if code == quien_pide:
            if dia == fecha:
                return True            # el día que pidió
            if dia in se_moveria:
                return False           # su descanso fijo se mueve a ese día
        if dia == fecha and code in aprobados_ese_dia:
            return True
        try:
            return estado_del_dia(h, dia) == DESCANSO
        except Exception:  # noqa: BLE001
            return False

    fuera, dentro = [], []
    for e in empleadas:
        code = _code(e.codigo)
        if code == quien_pide:
            continue
        (fuera if _descansa(code, fecha) else dentro).append(_pila(e.nombre_completo, code))

    semana = []
    lunes = fecha - timedelta(days=fecha.weekday())
    for i in range(7):
        dia = lunes + timedelta(days=i)
        descansan, trabajan = [], []
        for e in empleadas:
            code = _code(e.codigo)
            nombre = _pila(e.nombre_completo, code)
            if code == quien_pide and dia == fecha:
                nombre = f"{nombre} (lo pide)"
            (descansan if _descansa(code, dia) else trabajan).append(nombre)
        semana.append(DiaDeLaSemana(
            fecha=dia, nombre=_DIAS[dia.weekday()],
            trabajan=trabajan, descansan=descansan, es_el_pedido=(dia == fecha),
        ))

    venta, de_cuantos, mas_movido = _que_tan_movido(session, fecha)
    return Contexto(
        fecha=fecha,
        nombre_dia=_DIAS[fecha.weekday()],
        quien_mas_descansa=fuera,
        trabajan_ese_dia=dentro,
        semana=semana,
        venta_tipica=venta,
        venta_tipica_de_cuantos=de_cuantos,
        es_el_dia_mas_movido=mas_movido,
        tiene_pago=_le_toca_pago(session, quien_pide, fecha),
        tiene_conteo=_conteos_de(session, fecha),
    )


def _que_tan_movido(session: Session, fecha: date) -> tuple[Decimal | None, int, bool]:
    """(venta típica de ese día de la semana, de cuántas semanas, si es el pico).

    Se miran las semanas anteriores: un miércoles no se compara contra el
    sábado del mismo día, se compara contra los miércoles."""
    from pos_uniformes.database.models import LibretaVenta

    try:
        from sqlalchemy import func as sa_func

        desde = fecha - timedelta(weeks=SEMANAS_DE_REFERENCIA + 1)
        filas = session.query(
            LibretaVenta.created_at, LibretaVenta.monto_total
        ).filter(
            LibretaVenta.created_at >= datetime.combine(desde, datetime.min.time()).astimezone(),
            LibretaVenta.created_at < datetime.combine(fecha, datetime.min.time()).astimezone(),
        ).all()
        del sa_func
    except Exception:  # noqa: BLE001
        return None, 0, False

    por_dia: dict[date, Decimal] = {}
    for creado, monto in filas:
        if creado is None:
            continue
        dia = creado.astimezone().date() if creado.tzinfo else creado.date()
        por_dia[dia] = por_dia.get(dia, Decimal("0.00")) + Decimal(str(monto or 0))

    por_weekday: dict[int, list[Decimal]] = {}
    for dia, total in por_dia.items():
        por_weekday.setdefault(dia.weekday(), []).append(total)

    propios = por_weekday.get(fecha.weekday(), [])
    if not propios:
        return None, 0, False
    promedio = (sum(propios, Decimal("0.00")) / len(propios)).quantize(Decimal("0.01"))

    promedios = {
        wd: sum(v, Decimal("0.00")) / len(v) for wd, v in por_weekday.items() if v
    }
    # "El más movido" solo se dice si hay con qué comparar: con dos días
    # medidos, ser el mayor no significa nada.
    mas_movido = len(promedios) >= 5 and max(promedios, key=lambda wd: promedios[wd]) == fecha.weekday()
    return promedio, len(propios), mas_movido


def _le_toca_pago(session: Session, code: str, fecha: date) -> bool:
    from pos_uniformes.services.calendario_empleadas_service import (
        cargar_horario,
        fecha_proximo_pago,
    )

    try:
        return fecha_proximo_pago(cargar_horario(session, code), fecha) == fecha
    except Exception:  # noqa: BLE001
        return False


def _conteos_de(session: Session, fecha: date) -> list[str]:
    """Escuelas a las que les toca conteo ese día."""
    try:
        from pos_uniformes.services.conteo_calendario_service import obtener_calendario_conteo

        estados = obtener_calendario_conteo(session)
    except Exception:  # noqa: BLE001 — base sin el calendario de conteos
        return []
    return [
        str(e.escuela_nombre)
        for e in estados
        if getattr(e, "proxima_fecha", None) == fecha
    ]
