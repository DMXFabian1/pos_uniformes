"""Solicitudes de descanso: ella pide un día, Daniel lo aprueba desde el celular.

Mismo camino que los préstamos (pedir → aviso → aprobar/rechazar), con una
diferencia: aquí lo que Daniel necesita para decidir no es un monto, es cómo
queda la tienda ese día. Por eso `contexto_de(...)` arma lo que va en el aviso:
quién más descansa, la semana completa, qué tan movido suele ser ese día y si
ella tiene pago o conteo.

Al aprobar se marca el descanso con `marcar_dia`, que MUEVE el descanso fijo de
esa semana: no gana un día extra, cambia de día (Daniel, 2026-10-05).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import SolicitudDescanso

PEDIDO, APROBADO, RECHAZADO, CANCELADO = "pedido", "aprobado", "rechazado", "cancelado"

#: No se piden días que ya pasaron, y no se aparta el año entero.
DIAS_MAXIMO_ADELANTE = 60

#: Más de esto fuera el mismo día y la tienda se queda corta. No lo prohíbe
#: —Daniel decide—, pero el aviso lo dice fuerte.
CUANTAS_FUERA_INCOMODA = 2

#: Semanas atrás que se miran para decir si ese día de la semana es movido.
SEMANAS_DE_REFERENCIA = 4

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


class NoSePuede(Exception):
    """Algo impide la solicitud, con un mensaje que se le puede enseñar a ella."""


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _code(valor) -> str:
    return str(valor or "").strip().upper()


# ── Pedir ────────────────────────────────────────────────────────────────────

def pedir(
    session: Session, *, employee_code: str, nombre: str, fecha: date, motivo: str,
    hoy: date | None = None,
) -> SolicitudDescanso:
    """La empleada lo pide desde la Libreta. Queda esperando respuesta."""
    hoy = hoy or date.today()
    code = _code(employee_code)

    if fecha < hoy:
        raise NoSePuede("Ese día ya pasó. Pide uno de hoy en adelante.")
    if (fecha - hoy).days > DIAS_MAXIMO_ADELANTE:
        raise NoSePuede(
            f"Demasiado adelantado: lo más lejos que se puede pedir son "
            f"{DIAS_MAXIMO_ADELANTE} días."
        )
    motivo = (motivo or "").strip()
    if not motivo:
        raise NoSePuede("Escribe para qué lo necesitas: sin motivo no se puede autorizar.")

    if pendiente_de(session, code, fecha) is not None:
        raise NoSePuede("Ya pediste ese día y está esperando respuesta.")
    if _ya_aprobado(session, code, fecha):
        raise NoSePuede("Ese día ya te lo autorizaron.")
    if _es_su_descanso(session, code, fecha):
        raise NoSePuede("Ese día ya descansas: no hace falta pedirlo.")

    solicitud = SolicitudDescanso(
        employee_code=code, employee_name=str(nombre or ""),
        fecha=fecha, motivo=motivo[:200], estado=PEDIDO,
    )
    session.add(solicitud)
    session.flush()
    return solicitud


def _es_su_descanso(session: Session, code: str, fecha: date) -> bool:
    from pos_uniformes.services.calendario_empleadas_service import (
        DESCANSO,
        cargar_horario,
        estado_del_dia,
    )

    try:
        return estado_del_dia(cargar_horario(session, code), fecha) == DESCANSO
    except Exception:  # noqa: BLE001 — sin horario no se adivina nada
        return False


def _ya_aprobado(session: Session, code: str, fecha: date) -> bool:
    return session.scalars(
        select(SolicitudDescanso).where(
            SolicitudDescanso.employee_code == code,
            SolicitudDescanso.fecha == fecha,
            SolicitudDescanso.estado == APROBADO,
        )
    ).first() is not None


def pendiente_de(session: Session, employee_code: str, fecha: date | None = None):
    """La solicitud sin responder de esa persona (de un día, o la más próxima)."""
    stmt = select(SolicitudDescanso).where(
        SolicitudDescanso.employee_code == _code(employee_code),
        SolicitudDescanso.estado == PEDIDO,
    )
    if fecha is not None:
        stmt = stmt.where(SolicitudDescanso.fecha == fecha)
    return session.scalars(stmt.order_by(SolicitudDescanso.fecha)).first()


def pendientes(session: Session, *, hoy: date | None = None) -> list[SolicitudDescanso]:
    """Todas las que esperan respuesta, la más próxima primero.

    Las de días que YA pasaron no se listan: responder "sí" a un día que fue
    ayer no sirve de nada, y dejarlas ahí vuelve la lista un basurero. Siguen
    en la base como rastro de que se pidieron y nadie contestó."""
    hoy = hoy or date.today()
    return list(session.scalars(
        select(SolicitudDescanso)
        .where(SolicitudDescanso.estado == PEDIDO, SolicitudDescanso.fecha >= hoy)
        .order_by(SolicitudDescanso.fecha, SolicitudDescanso.id)
    ).all())


def sin_responder_que_ya_pasaron(session: Session, *, hoy: date | None = None) -> list[SolicitudDescanso]:
    """Las que se quedaron sin respuesta hasta que el día pasó.

    Importa saberlo: desde el lado de ella, no contestar se siente igual que un
    "no", pero sin que nadie lo haya decidido."""
    hoy = hoy or date.today()
    return list(session.scalars(
        select(SolicitudDescanso)
        .where(SolicitudDescanso.estado == PEDIDO, SolicitudDescanso.fecha < hoy)
        .order_by(SolicitudDescanso.fecha)
    ).all())


# ── Responder ────────────────────────────────────────────────────────────────

def _viva(session: Session, solicitud_id: int) -> SolicitudDescanso:
    solicitud = session.get(SolicitudDescanso, int(solicitud_id))
    if solicitud is None:
        raise NoSePuede("Esa solicitud ya no existe.")
    if solicitud.estado != PEDIDO:
        raise NoSePuede(f"Esa solicitud ya está {solicitud.estado}.")
    return solicitud


def aprobar(session: Session, solicitud_id: int, *, quien: str, respuesta: str = "") -> SolicitudDescanso:
    """Le das el día: se marca en el calendario y su descanso fijo se mueve.

    `marcar_dia` ya hace lo de mover el fijo de esa semana, que es justo lo que
    Daniel quiere: cambia de día, no gana uno extra."""
    from pos_uniformes.services.calendario_empleadas_service import DESCANSO, marcar_dia

    solicitud = _viva(session, solicitud_id)
    solicitud.estado = APROBADO
    solicitud.resuelto_por = _code(quien)
    solicitud.resuelto_at = _ahora()
    solicitud.respuesta = (respuesta or "").strip()[:200] or None
    session.add(solicitud)
    session.flush()
    # El evento del calendario se escribe SOLO aquí: hasta ahora era una
    # petición, y una petición no es un día libre.
    marcar_dia(
        session, solicitud.employee_code, solicitud.fecha, DESCANSO,
        nota=f"Lo pidió ella: {solicitud.motivo}"[:200],
    )
    return solicitud


def rechazar(session: Session, solicitud_id: int, *, quien: str, respuesta: str = "") -> SolicitudDescanso:
    """No se le da el día. Nada se escribe en el calendario."""
    solicitud = _viva(session, solicitud_id)
    solicitud.estado = RECHAZADO
    solicitud.resuelto_por = _code(quien)
    solicitud.resuelto_at = _ahora()
    solicitud.respuesta = (respuesta or "").strip()[:200] or None
    session.add(solicitud)
    session.flush()
    return solicitud


def cancelar(session: Session, solicitud_id: int, *, quien: str) -> SolicitudDescanso:
    """Ella se arrepiente antes de que le contesten."""
    solicitud = _viva(session, solicitud_id)
    if _code(quien) != solicitud.employee_code:
        raise NoSePuede("Solo quien la pidió puede cancelarla.")
    solicitud.estado = CANCELADO
    solicitud.resuelto_at = _ahora()
    session.add(solicitud)
    session.flush()
    return solicitud


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
    if horario_pide is not None:
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
