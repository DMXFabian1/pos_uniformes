"""Vacaciones: un módulo aparte de los descansos (Daniel, 2026-10-12).

Se integra con el calendario (eventos tipo "vacaciones", ligados a su
solicitud) y con la nómina (días pagados, no trabajados, nunca falta), pero
tiene su propio ciclo de vida, saldo y bitácora, y NO gasta los dos cambios
de descanso del mes.

Ley Federal del Trabajo (reforma «vacaciones dignas», DOF 27-12-2022, vigente
desde 2023; verificado el 2026-10-12 en fuentes secundarias):
- Art. 76: con más de un año de servicios, al menos 12 días LABORABLES; +2 por
  cada año siguiente hasta 20; desde el sexto año, +2 por cada cinco años.
- Art. 78: al menos 12 días continuos; el resto, como ella decida. Aquí se
  INFORMA (no se le prohíbe pedir menos: es un derecho de ella, no un candado).
- Art. 79: no se cambian por dinero (salvo al terminar la relación: fuera de
  este módulo).
- Art. 80: prima vacacional de al menos 25 % sobre los salarios del periodo.
- Art. 81: se conceden dentro de los seis meses siguientes al aniversario.

Lo que es POLÍTICA de la tienda (no ley) está en constantes y se dice como
tal. Lo que necesita revisión de un contador está marcado «REVISAR».

Saldo: NUNCA se guarda; se reconstruye sumando `movimiento_vacaciones`:
generacion (+), reserva (al aprobar), liberacion (al cancelar/revocar),
consumo (al pasar cada día), ajuste (±, con motivo).

Sin expediente (fecha de ingreso capturada y verificada por Daniel) no hay
periodos ni saldo: el expediente sale «pendiente de completar».

Quién lo usa (Daniel, 2026-10-12): por ahora SOLO Daniel, desde su Libreta
(`registrar_por_dueno`). Cada empleada puede pedirlas ella misma únicamente
cuando Daniel le abre el autoservicio (`habilitar_autoservicio`), una por
una, conforme vea que no hay fallos. La regla vive aquí, no solo en el botón.

Ninguna función hace commit: quien llama confirma todo junto o nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    ExpedienteVacacional,
    MovimientoVacaciones,
    PeriodoVacaciones,
    PrimaVacacional,
    SolicitudVacaciones,
)

PEDIDO, APROBADO, RECHAZADO, CANCELADO = "pedido", "aprobado", "rechazado", "cancelado"
VENCIDO, REVOCADO = "vencido", "revocado"
TRANSICIONES = {
    PEDIDO: frozenset({APROBADO, RECHAZADO, CANCELADO, VENCIDO}),
    APROBADO: frozenset({REVOCADO, CANCELADO}),
}

GENERACION, RESERVA, LIBERACION, CONSUMO, AJUSTE = (
    "generacion", "reserva", "liberacion", "consumo", "ajuste"
)
PRIMA_PENDIENTE, PRIMA_PAGADA, PRIMA_CANCELADA = "pendiente", "pagada", "cancelada"

# ── Ley ──────────────────────────────────────────────────────────────────────
#: Art. 78: días continuos mínimos del periodo (se informa, no se impone).
DIAS_CONTINUOS_MINIMOS = 12
#: Art. 81: meses para conceder las vacaciones tras el aniversario.
MESES_PARA_CONCEDER = 6
#: Art. 80: la prima es AL MENOS esto.
PORCENTAJE_PRIMA = Decimal("25")

# ── Política de la tienda (NO es ley; Daniel la define) ──────────────────────
#: Días naturales de anticipación para pedir. None = sin mínimo (Daniel,
#: 2026-10-12: queda apagado hasta que se defina).
#: Daniel, 2026-10-13: «lo de vacaciones lo dejaremos oculto o en
#: construcción; quiero que lo de ellas siga funcionando como hasta ahora».
#: Con esto en True no se ve en la Libreta (ni el panel de Daniel), el bot
#: contesta «en construcción» a /vacaciones, /primas e /ingreso, el menú no
#: lo ofrece y el vigilante no genera periodos. El código y las tablas se
#: quedan; para estrenarlo, poner False.
EN_CONSTRUCCION = True
EN_CONSTRUCCION_TEXTO = "🏗️ Vacaciones todavía está en construcción. Por ahora no se usa."

ANTICIPACION_VACACIONES_DIAS: int | None = None
#: Cuántas pueden estar de vacaciones el mismo día (cobertura).
MAX_DE_VACACIONES_POR_DIA = 1
#: Salario diario para la prima = sueldo del ciclo / 7 (el séptimo día se
#: paga). REVISAR con el contador: si las comisiones entran al salario (LFT
#: art. 89, salario variable) la base cambia. Hoy NO las incluye.
DIAS_SALARIO_SEMANAL = 7

_CENT = Decimal("0.01")
_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_CANDADO = 734_002_612


class NoSePuede(Exception):
    """Algo impide la operación, con un mensaje que se le puede enseñar."""


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _code(valor) -> str:
    return str(valor or "").strip().upper()


def _dd(d: date) -> str:
    return f"{_DIAS[d.weekday()]} {d:%d/%m}"


def _bloquear(session: Session) -> None:
    """Dos solicitudes al mismo tiempo no gastan el mismo saldo."""
    try:
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CANDADO})
    except Exception:  # noqa: BLE001
        pass


# ── Ley (puro) ───────────────────────────────────────────────────────────────

def dias_por_anio_de_servicio(anio: int) -> int:
    """LFT art. 76 (2023). `anio` = años de servicio cumplidos (1, 2, ...)."""
    if anio < 1:
        return 0
    if anio <= 5:
        return 12 + 2 * (anio - 1)
    return 20 + 2 * ((anio - 1) // 5)


def _sumar_anios(d: date, anios: int) -> date:
    try:
        return d.replace(year=d.year + anios)
    except ValueError:  # 29 de febrero
        return d.replace(year=d.year + anios, day=28)


def _sumar_meses(d: date, meses: int) -> date:
    from calendar import monthrange

    y, m = divmod(d.month - 1 + meses, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def salario_diario(sueldo_ciclo: Decimal) -> Decimal:
    return (Decimal(str(sueldo_ciclo)) / DIAS_SALARIO_SEMANAL).quantize(_CENT)


def prima_vacacional(sueldo_ciclo: Decimal, dias: int) -> Decimal:
    """Art. 80: prima = % × salario diario × días de vacaciones."""
    diario = Decimal(str(sueldo_ciclo)) / DIAS_SALARIO_SEMANAL
    return (diario * dias * PORCENTAJE_PRIMA / 100).quantize(_CENT)


# ── Expediente y periodos ────────────────────────────────────────────────────

def capturar_expediente(session: Session, employee_code: str, *, fecha_ingreso: date,
                        quien: str, antiguedad_desde: date | None = None,
                        condiciones_especiales: str | None = None,
                        nota: str | None = None, origen: str = "admin") -> ExpedienteVacacional:
    """Daniel captura la fecha de ingreso VERIFICADA. No se puede mover si ya
    hay periodos generados (moverías saldos ya usados): eso es un ajuste."""
    code = _code(employee_code)
    if antiguedad_desde is not None and antiguedad_desde > fecha_ingreso:
        raise NoSePuede("La antigüedad reconocida no puede ser posterior al ingreso.")
    exp = session.get(ExpedienteVacacional, code)
    antes = None
    if exp is not None:
        antes = {"fecha_ingreso": exp.fecha_ingreso.isoformat(),
                 "antiguedad_desde": exp.antiguedad_desde.isoformat() if exp.antiguedad_desde else None}
        cambia = (exp.fecha_ingreso, exp.antiguedad_desde) != (fecha_ingreso, antiguedad_desde)
        hay = session.query(PeriodoVacaciones).filter(PeriodoVacaciones.employee_code == code).count()
        if cambia and hay:
            raise NoSePuede("Ya hay periodos generados con la fecha anterior; corrige con un ajuste.")
    if exp is None:
        exp = ExpedienteVacacional(employee_code=code, fecha_ingreso=fecha_ingreso,
                                   capturado_por=_code(quien))
        session.add(exp)
    exp.fecha_ingreso = fecha_ingreso
    exp.antiguedad_desde = antiguedad_desde
    exp.condiciones_especiales = (condiciones_especiales or "").strip()[:300] or None
    exp.nota = (nota or "").strip()[:200] or None
    exp.capturado_por = _code(quien)
    session.flush()
    _auditar(session, "expediente", code, quien, origen=origen, antes=antes,
             despues={"fecha_ingreso": fecha_ingreso.isoformat(),
                      "antiguedad_desde": antiguedad_desde.isoformat() if antiguedad_desde else None,
                      "condiciones_especiales": exp.condiciones_especiales})
    return exp


def _inicio_antiguedad(exp: ExpedienteVacacional) -> date:
    return exp.antiguedad_desde or exp.fecha_ingreso


def generar_periodos(session: Session, employee_code: str, *, hoy: date | None = None,
                     quien: str = "sistema") -> list[PeriodoVacaciones]:
    """Crea los periodos de cada año de servicio YA cumplido que falten (desde
    su aniversario, no desde enero). Idempotente."""
    hoy = hoy or date.today()
    code = _code(employee_code)
    exp = session.get(ExpedienteVacacional, code)
    if exp is None:
        return []
    inicio = _inicio_antiguedad(exp)
    existentes = {
        p.anio_servicio for p in session.scalars(
            select(PeriodoVacaciones).where(PeriodoVacaciones.employee_code == code)
        ).all()
    }
    nuevos = []
    anio = 1
    while (aniversario := _sumar_anios(inicio, anio)) <= hoy:
        if anio not in existentes:
            dias = dias_por_anio_de_servicio(anio)
            p = PeriodoVacaciones(
                employee_code=code, anio_servicio=anio, aniversario=aniversario,
                fecha_limite=_sumar_meses(aniversario, MESES_PARA_CONCEDER),
                dias_correspondientes=dias,
            )
            session.add(p)
            session.flush()
            session.add(MovimientoVacaciones(
                employee_code=code, periodo_id=p.id, tipo=GENERACION, dias=dias,
                actor=_code(quien), motivo=f"año {anio} de servicio (LFT art. 76)",
            ))
            nuevos.append(p)
        anio += 1
    session.flush()
    return nuevos


@dataclass(frozen=True)
class Saldo:
    generado: int
    reservado: int
    disfrutado: int

    @property
    def disponible(self) -> int:
        return self.generado - self.reservado - self.disfrutado


def saldo(session: Session, employee_code: str, *, periodo_id: int | None = None) -> Saldo:
    """Se reconstruye de los movimientos, siempre."""
    q = session.query(MovimientoVacaciones).filter(
        MovimientoVacaciones.employee_code == _code(employee_code)
    )
    if periodo_id is not None:
        q = q.filter(MovimientoVacaciones.periodo_id == periodo_id)
    suma = {GENERACION: 0, RESERVA: 0, LIBERACION: 0, CONSUMO: 0, AJUSTE: 0}
    for m in q.all():
        suma[m.tipo] += m.dias
    return Saldo(
        generado=suma[GENERACION] + suma[AJUSTE],
        reservado=suma[RESERVA] - suma[LIBERACION] - suma[CONSUMO],
        disfrutado=suma[CONSUMO],
    )


@dataclass
class PeriodoVista:
    periodo: PeriodoVacaciones
    saldo: Saldo
    pedidos: int
    continuo_max: int

    @property
    def cumple_art_78(self) -> bool:
        return self.continuo_max >= min(DIAS_CONTINUOS_MINIMOS, self.periodo.dias_correspondientes)


@dataclass
class Expediente:
    """Todo lo de una empleada, para la Libreta, Telegram y el Calendario."""

    employee_code: str
    completo: bool
    falta: list[str] = field(default_factory=list)
    autoservicio: bool = False
    condiciones_especiales: str | None = None
    fecha_ingreso: date | None = None
    antiguedad_desde: date | None = None
    anios_cumplidos: int = 0
    revisar: str | None = None
    periodos: list[PeriodoVista] = field(default_factory=list)
    solicitudes: list[SolicitudVacaciones] = field(default_factory=list)
    ajustes: list[MovimientoVacaciones] = field(default_factory=list)
    primas: list[PrimaVacacional] = field(default_factory=list)

    @property
    def disponible(self) -> int:
        return sum(p.saldo.disponible for p in self.periodos)


def expediente(session: Session, employee_code: str, *, hoy: date | None = None) -> Expediente:
    hoy = hoy or date.today()
    code = _code(employee_code)
    exp = session.get(ExpedienteVacacional, code)
    if exp is None:
        return Expediente(code, completo=False, falta=["fecha de ingreso verificada"])
    inicio = _inicio_antiguedad(exp)
    anios = 0
    while _sumar_anios(inicio, anios + 1) <= hoy:
        anios += 1
    periodos = []
    for p in session.scalars(select(PeriodoVacaciones).where(
        PeriodoVacaciones.employee_code == code).order_by(PeriodoVacaciones.anio_servicio)).all():
        pedidos = sum(s.dias for s in session.scalars(select(SolicitudVacaciones).where(
            SolicitudVacaciones.periodo_id == p.id, SolicitudVacaciones.estado == PEDIDO)).all())
        periodos.append(PeriodoVista(p, saldo(session, code, periodo_id=p.id), pedidos,
                                     _continuo_max(session, p.id)))
    return Expediente(
        employee_code=code, completo=True, fecha_ingreso=exp.fecha_ingreso,
        autoservicio=bool(exp.autoservicio),
        condiciones_especiales=exp.condiciones_especiales,
        antiguedad_desde=exp.antiguedad_desde, anios_cumplidos=anios,
        revisar=(f"Tiene condiciones especiales: {exp.condiciones_especiales}. "
                 "El mínimo de ley no las sustituye; revisar a mano.")
        if exp.condiciones_especiales else None,
        periodos=periodos,
        solicitudes=list(session.scalars(select(SolicitudVacaciones).where(
            SolicitudVacaciones.employee_code == code).order_by(SolicitudVacaciones.desde.desc())).all()),
        ajustes=list(session.scalars(select(MovimientoVacaciones).where(
            MovimientoVacaciones.employee_code == code, MovimientoVacaciones.tipo == AJUSTE)).all()),
        primas=list(session.scalars(select(PrimaVacacional).where(
            PrimaVacacional.employee_code == code).order_by(PrimaVacacional.id)).all()),
    )


def _continuo_max(session, periodo_id: int) -> int:
    """El tramo más largo de vacaciones aprobadas de ese periodo (art. 78):
    días de vacaciones seguidos, sin contar como corte sus descansos."""
    mejor = 0
    for s in session.scalars(select(SolicitudVacaciones).where(
        SolicitudVacaciones.periodo_id == periodo_id,
        SolicitudVacaciones.estado == APROBADO,
    )).all():
        mejor = max(mejor, s.dias)
    return mejor


def ajustar(session: Session, employee_code: str, periodo_id: int, dias: int, *,
            quien: str, motivo: str, permitir_negativo: bool = False) -> MovimientoVacaciones:
    """Corrección administrativa, con motivo y en la bitácora."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise NoSePuede("El ajuste necesita motivo.")
    code = _code(employee_code)
    m = MovimientoVacaciones(employee_code=code, periodo_id=periodo_id, tipo=AJUSTE,
                             dias=int(dias), actor=_code(quien), motivo=motivo[:200])
    session.add(m)
    session.flush()
    if saldo(session, code, periodo_id=periodo_id).disponible < 0 and not permitir_negativo:
        raise NoSePuede("El ajuste dejaría el saldo en negativo.")
    _auditar(session, "ajuste", code, quien, despues={"periodo_id": periodo_id, "dias": dias},
             motivo=motivo)
    return m


# ── Calendario ───────────────────────────────────────────────────────────────

def dias_laborables(horario, desde: date, hasta: date) -> list[date]:
    """Los días del rango que le tocaría trabajar (sus descansos no cuentan)."""
    from pos_uniformes.services.calendario_empleadas_service import DESCANSO, estado_del_dia

    dias, d = [], desde
    while d <= hasta:
        if horario.por_dia:
            if d.weekday() in horario.dias_trabajo:
                dias.append(d)
        elif estado_del_dia(horario, d) != DESCANSO:
            dias.append(d)
        d += timedelta(days=1)
    return dias


def _conflictos(session, code: str, dias: list[date], *, excluir_id=None) -> None:
    """Lo que choca: sus faltas/pagos/vacaciones, sus descansos pedidos, y
    otra compañera de vacaciones esos días."""
    from pos_uniformes.database.models import SolicitudDescanso
    from pos_uniformes.services.calendario_empleadas_service import (
        FALTA, PAGO, VACACIONES, cargar_horario,
    )

    h = cargar_horario(session, code)
    for d in dias:
        if h.eventos.get(d) in (FALTA, VACACIONES) or d in h.pagos or h.eventos.get(d) == PAGO:
            raise NoSePuede(f"El {_dd(d)} ya tiene otra marca ({h.eventos.get(d)}).")
    if not dias:
        return
    desc = session.scalars(select(SolicitudDescanso).where(
        SolicitudDescanso.estado.in_(("pedido", "aprobado")),
        SolicitudDescanso.employee_code == code,
        SolicitudDescanso.fecha.between(min(dias), max(dias)),
    )).first()
    if desc is not None:
        raise NoSePuede(f"Tiene un descanso pedido o autorizado el {desc.fecha:%d/%m}.")
    q = select(SolicitudVacaciones).where(
        SolicitudVacaciones.estado.in_((PEDIDO, APROBADO)),
        SolicitudVacaciones.desde <= max(dias),
        SolicitudVacaciones.hasta >= min(dias),
    )
    if excluir_id is not None:
        q = q.where(SolicitudVacaciones.id != excluir_id)
    otras = session.scalars(q).all()
    if any(_code(o.employee_code) == code for o in otras):
        raise NoSePuede("Ya tiene vacaciones pedidas o aprobadas que se cruzan.")
    if len(otras) >= MAX_DE_VACACIONES_POR_DIA:
        raise NoSePuede(
            f"Esos días ya está de vacaciones {otras[0].employee_name or otras[0].employee_code}."
        )


def cobertura(session, desde: date, hasta: date, *, excluir: str = "") -> dict[date, list[str]]:
    """Quién más está fuera (descanso o vacaciones) cada día del rango. Para
    que Daniel decida: no bloquea nada."""
    from pos_uniformes.services.calendario_empleadas_service import (
        DESCANSO, VACACIONES, cargar_horarios_todos, estado_del_dia,
    )

    horarios = cargar_horarios_todos(session)
    salida: dict[date, list[str]] = {}
    d = desde
    while d <= hasta:
        salida[d] = sorted(
            c for c, h in horarios.items()
            if c != _code(excluir) and estado_del_dia(h, d) in (DESCANSO, VACACIONES)
            and not (h.por_dia and estado_del_dia(h, d) == DESCANSO)
        )
        d += timedelta(days=1)
    return salida


def _periodo_con_saldo(session, code: str, dias: int) -> PeriodoVacaciones:
    periodos = session.scalars(
        select(PeriodoVacaciones).where(PeriodoVacaciones.employee_code == code)
        .order_by(PeriodoVacaciones.anio_servicio)
    ).all()
    if not periodos:
        raise NoSePuede(
            "Todavía no tiene vacaciones generadas: falta su fecha de ingreso o cumplir el primer año."
        )
    for p in periodos:
        pendientes = sum(
            s.dias for s in session.scalars(select(SolicitudVacaciones).where(
                SolicitudVacaciones.periodo_id == p.id, SolicitudVacaciones.estado == PEDIDO,
            )).all()
        )
        if saldo(session, code, periodo_id=p.id).disponible - pendientes >= dias:
            return p
    raise NoSePuede("No le alcanzan los días de un mismo periodo; pide menos días.")


# ── Solicitudes ──────────────────────────────────────────────────────────────

def pedir(session: Session, *, employee_code: str, nombre: str, desde: date, hasta: date,
          motivo: str = "", hoy: date | None = None, origen: str = "kiosko",
          por_dueno: bool = False) -> SolicitudVacaciones:
    """Ella las pide (solo si Daniel ya le abrió el autoservicio). NO descuenta
    saldo: lo aparta para que otra solicitud no lo use; se reserva al aprobar."""
    from pos_uniformes.services.calendario_empleadas_service import cargar_horario

    hoy = hoy or date.today()
    code = _code(employee_code)
    _bloquear(session)
    vencer_pendientes(session, hoy=hoy)
    if not por_dueno:
        exp = session.get(ExpedienteVacacional, code)
        if exp is None or not exp.autoservicio:
            raise NoSePuede("Por ahora tus vacaciones las registra Daniel. Pídeselas a él.")
    if hasta < desde:
        raise NoSePuede("El último día va después del primero.")
    if desde < hoy:
        raise NoSePuede("No se piden vacaciones en días que ya pasaron.")
    if (not por_dueno and ANTICIPACION_VACACIONES_DIAS
            and (desde - hoy).days < ANTICIPACION_VACACIONES_DIAS):
        raise NoSePuede(
            f"Las vacaciones se piden con {ANTICIPACION_VACACIONES_DIAS} días de anticipación."
        )
    dias = dias_laborables(cargar_horario(session, code), desde, hasta)
    if not dias:
        raise NoSePuede("En ese rango no hay días que le toque trabajar.")
    _conflictos(session, code, dias)
    periodo = _periodo_con_saldo(session, code, len(dias))
    s = SolicitudVacaciones(
        employee_code=code, employee_name=str(nombre or ""), periodo_id=periodo.id,
        desde=desde, hasta=hasta, dias=len(dias), estado=PEDIDO,
        motivo=(motivo or "").strip()[:200] or None, origen=origen,
    )
    session.add(s)
    session.flush()
    _auditar(session, "pedir", code, code, solicitud=s, origen=origen,
             despues={"desde": desde.isoformat(), "hasta": hasta.isoformat(), "dias": len(dias)})
    return s


def registrar_por_dueno(session: Session, *, employee_code: str, nombre: str, desde: date,
                       hasta: date, quien: str, motivo: str = "",
                       hoy: date | None = None) -> SolicitudVacaciones:
    """Daniel registra las vacaciones de alguien desde su Libreta: se piden y
    se aprueban en la misma transacción, con todas las validaciones (saldo,
    conflictos, cobertura) y la prima pendiente."""
    from pos_uniformes.services.nomina_service import OWNER_CODE

    if _code(quien) != OWNER_CODE:
        raise NoSePuede("Las vacaciones por ahora solo las registra Daniel.")
    s = pedir(session, employee_code=employee_code, nombre=nombre, desde=desde, hasta=hasta,
              motivo=motivo, hoy=hoy, origen="libreta", por_dueno=True)
    return aprobar(session, s.id, quien=quien, hoy=hoy, origen="libreta")


def habilitar_autoservicio(session: Session, employee_code: str, habilitado: bool, *,
                           quien: str) -> ExpedienteVacacional:
    """Daniel le abre (o le cierra) pedir vacaciones desde su propia Libreta."""
    from pos_uniformes.services.nomina_service import OWNER_CODE

    if _code(quien) != OWNER_CODE:
        raise NoSePuede("Solo Daniel decide quién pide sus vacaciones.")
    code = _code(employee_code)
    exp = session.get(ExpedienteVacacional, code)
    if exp is None:
        raise NoSePuede("Primero captura su fecha de ingreso.")
    antes = bool(exp.autoservicio)
    exp.autoservicio = bool(habilitado)
    session.flush()
    _auditar(session, "autoservicio", code, quien, origen="libreta",
             antes={"autoservicio": antes}, despues={"autoservicio": bool(habilitado)})
    return exp


def equipo(session: Session, *, hoy: date | None = None) -> list[tuple[str, str, "Expediente"]]:
    """(código, nombre, expediente) de cada empleada activa (sin dueño ni
    encargado), para el panel de Daniel."""
    from pos_uniformes.database.models import Empleada
    from pos_uniformes.services.nomina_service import QUIEN_PUEDE_PAGAR

    salida = []
    for e in session.query(Empleada).filter(Empleada.activo.is_(True)).order_by(Empleada.nombre_completo):
        code = _code(e.codigo)
        if code in QUIEN_PUEDE_PAGAR:
            continue
        salida.append((code, e.nombre_completo or code, expediente(session, code, hoy=hoy)))
    return salida


def _viva(session, sid: int, *estados: str) -> SolicitudVacaciones:
    s = session.get(SolicitudVacaciones, int(sid))
    if s is None:
        raise NoSePuede("Esa solicitud ya no existe.")
    if s.estado not in (estados or (PEDIDO,)):
        raise NoSePuede(f"Esa solicitud ya está {s.estado}.")
    return s


def _transicion(session, s, nuevo, *, quien, motivo=None, despues=None, origen="admin") -> None:
    if nuevo not in TRANSICIONES.get(s.estado, ()):
        raise NoSePuede(f"Esa solicitud ya está {s.estado}.")
    antes = s.estado
    s.estado = nuevo
    s.resuelto_at = s.resuelto_at or _ahora()
    if quien and nuevo in (APROBADO, RECHAZADO):
        s.resuelto_por = _code(quien)
    if nuevo in (RECHAZADO, VENCIDO, REVOCADO) or (nuevo == CANCELADO and _code(quien) != _code(s.employee_code)):
        s.avisada_at = None     # se le tiene que decir
    session.flush()
    _auditar(session, nuevo, s.employee_code, quien, solicitud=s, origen=origen,
             antes={"estado": antes}, despues={"estado": nuevo, **(despues or {})}, motivo=motivo)


def aprobar(session: Session, sid: int, *, quien: str, hoy: date | None = None,
            respuesta: str = "", origen: str = "telegram") -> SolicitudVacaciones:
    """Reserva los días, los pinta en el calendario y deja la prima pendiente:
    todo o nada. Un botón viejo encuentra la solicitud resuelta."""
    from pos_uniformes.database.models import CajaParametros, EmpleadaEvento
    from pos_uniformes.services.calendario_empleadas_service import VACACIONES, cargar_horario

    hoy = hoy or date.today()
    _bloquear(session)
    s = _viva(session, sid)
    if s.desde < hoy:
        raise NoSePuede("Ese rango ya empezó: se cierra como vencida.")
    dias = dias_laborables(cargar_horario(session, s.employee_code), s.desde, s.hasta)
    if len(dias) != s.dias:
        raise NoSePuede("Su calendario cambió desde que lo pidió; que lo vuelva a pedir.")
    _conflictos(session, _code(s.employee_code), dias, excluir_id=s.id)
    if saldo(session, s.employee_code, periodo_id=s.periodo_id).disponible < s.dias:
        raise NoSePuede("Ya no le alcanzan los días de ese periodo.")
    session.add(MovimientoVacaciones(
        employee_code=s.employee_code, periodo_id=s.periodo_id, solicitud_id=s.id,
        tipo=RESERVA, dias=s.dias, actor=_code(quien), motivo="aprobada",
    ))
    for d in dias:
        session.add(EmpleadaEvento(employee_code=s.employee_code, fecha=d, tipo=VACACIONES,
                                   nota=f"vacaciones (solicitud {s.id})", vacacion_id=s.id))
    params = session.query(CajaParametros).first()
    if params is not None and Decimal(str(params.sueldo_base or 0)) > 0:
        monto = prima_vacacional(params.sueldo_base, s.dias)
        s.prima_estimada = monto
        session.add(PrimaVacacional(
            solicitud_id=s.id, employee_code=s.employee_code, dias=s.dias,
            salario_diario=salario_diario(params.sueldo_base), porcentaje=PORCENTAJE_PRIMA,
            monto=monto, estado=PRIMA_PENDIENTE,
        ))
    s.respuesta = (respuesta or "").strip()[:200] or None
    s.avisada_at = None
    _transicion(session, s, APROBADO, quien=quien, origen=origen,
                despues={"dias": [d.isoformat() for d in dias]})
    return s


def rechazar(session: Session, sid: int, *, quien: str, respuesta: str = "",
             origen: str = "telegram") -> SolicitudVacaciones:
    s = _viva(session, sid)
    s.respuesta = (respuesta or "").strip()[:200] or None
    _transicion(session, s, RECHAZADO, quien=quien, motivo=s.respuesta, origen=origen)
    return s


def _devolver_lo_no_disfrutado(session, s, *, quien: str, hoy: date, motivo: str) -> int:
    """Quita del calendario los días que no han pasado, libera esos días y
    ajusta la prima a lo que sí se disfrutó."""
    from pos_uniformes.database.models import EmpleadaEvento

    consumir(session, s.id, hoy=hoy, quien=quien)   # lo ya disfrutado se consume
    futuros = session.query(EmpleadaEvento).filter(
        EmpleadaEvento.vacacion_id == s.id, EmpleadaEvento.fecha >= hoy,
    ).all()
    for ev in futuros:
        session.delete(ev)
    if futuros:
        session.add(MovimientoVacaciones(
            employee_code=s.employee_code, periodo_id=s.periodo_id, solicitud_id=s.id,
            tipo=LIBERACION, dias=len(futuros), actor=_code(quien), motivo=motivo[:200],
        ))
    session.flush()
    _ajustar_prima(session, s, dias_disfrutados=s.dias - len(futuros), quien=quien)
    return len(futuros)


def _ajustar_prima(session, s, *, dias_disfrutados: int, quien: str) -> None:
    prima = session.scalars(select(PrimaVacacional).where(PrimaVacacional.solicitud_id == s.id)).first()
    if prima is None:
        return
    if prima.estado == PRIMA_PAGADA:
        if dias_disfrutados < prima.dias:
            # Ya se pagó: no se toca la nómina histórica. Queda dicho para que
            # Daniel decida con una operación explícita.
            prima.nota = (f"Pagada sobre {prima.dias} días; se disfrutaron {dias_disfrutados}. "
                          "Revisar a mano.")[:200]
            _auditar(session, "prima_revisar", s.employee_code, quien, solicitud=s,
                     despues={"pagada_dias": prima.dias, "disfrutados": dias_disfrutados})
        return
    if dias_disfrutados <= 0:
        prima.estado = PRIMA_CANCELADA
        prima.nota = "vacaciones canceladas antes de disfrutarse"
    else:
        prima.dias = dias_disfrutados
        prima.monto = (prima.salario_diario * dias_disfrutados * prima.porcentaje / 100).quantize(_CENT)
    session.flush()


def cancelar(session: Session, sid: int, *, quien: str, hoy: date | None = None,
             motivo: str = "cancelada", origen: str = "kiosko") -> SolicitudVacaciones:
    """Pedida: ella la retira. Aprobada: devuelve los días no disfrutados
    (si ya empezó, lo disfrutado se queda como disfrutado)."""
    hoy = hoy or date.today()
    _bloquear(session)
    s = _viva(session, sid, PEDIDO, APROBADO)
    if s.estado == PEDIDO and _code(quien) != _code(s.employee_code):
        raise NoSePuede("Solo ella retira su solicitud; Daniel la rechaza.")
    devueltos = 0
    if s.estado == APROBADO:
        devueltos = _devolver_lo_no_disfrutado(session, s, quien=quien, hoy=hoy, motivo=motivo)
    _transicion(session, s, CANCELADO, quien=quien, motivo=motivo, origen=origen,
                despues={"dias_devueltos": devueltos})
    return s


def revocar(session: Session, sid: int, *, quien: str, motivo: str,
            hoy: date | None = None, origen: str = "admin") -> SolicitudVacaciones:
    if not (motivo or "").strip():
        raise NoSePuede("Para revocar hace falta el motivo.")
    hoy = hoy or date.today()
    s = _viva(session, sid, APROBADO)
    devueltos = _devolver_lo_no_disfrutado(session, s, quien=quien, hoy=hoy, motivo=motivo)
    _transicion(session, s, REVOCADO, quien=quien, motivo=motivo, origen=origen,
                despues={"dias_devueltos": devueltos})
    return s


def consumir(session: Session, sid: int | None = None, *, hoy: date | None = None,
             quien: str = "sistema") -> int:
    """Registro del disfrute efectivo: los días de vacaciones que ya pasaron se
    vuelven disfrutados (una sola vez)."""
    from pos_uniformes.database.models import EmpleadaEvento

    hoy = hoy or date.today()
    q = select(SolicitudVacaciones).where(SolicitudVacaciones.estado == APROBADO)
    if sid is not None:
        q = q.where(SolicitudVacaciones.id == sid)
    total = 0
    for s in session.scalars(q).all():
        pasados = session.query(EmpleadaEvento).filter(
            EmpleadaEvento.vacacion_id == s.id, EmpleadaEvento.fecha < hoy,
        ).count()
        ya = sum(m.dias for m in session.scalars(select(MovimientoVacaciones).where(
            MovimientoVacaciones.solicitud_id == s.id, MovimientoVacaciones.tipo == CONSUMO,
        )).all())
        if pasados > ya:
            session.add(MovimientoVacaciones(
                employee_code=s.employee_code, periodo_id=s.periodo_id, solicitud_id=s.id,
                tipo=CONSUMO, dias=pasados - ya, actor=_code(quien), motivo="días disfrutados",
            ))
            total += pasados - ya
    session.flush()
    return total


def vencer_pendientes(session: Session, *, hoy: date | None = None) -> list[SolicitudVacaciones]:
    hoy = hoy or date.today()
    viejas = session.scalars(select(SolicitudVacaciones).where(
        SolicitudVacaciones.estado == PEDIDO, SolicitudVacaciones.desde < hoy,
    )).all()
    for s in viejas:
        _transicion(session, s, VENCIDO, quien=None, motivo="nadie la contestó a tiempo",
                    origen="sistema")
    return list(viejas)


def revocar_por_calendario(session: Session, sid: int, *, quien: str, fecha: date) -> None:
    """Alguien quitó o remarcó un día de vacaciones desde el calendario: la
    solicitud no se queda apuntando a días que ya no existen."""
    s = session.get(SolicitudVacaciones, int(sid))
    if s is None or s.estado != APROBADO:
        return
    revocar(session, sid, quien=quien, motivo=f"se cambió el {fecha:%d/%m} desde el calendario",
            hoy=fecha, origen="calendario")


# ── Prima y nómina ───────────────────────────────────────────────────────────

def primas_pendientes(session: Session) -> list[PrimaVacacional]:
    return list(session.scalars(select(PrimaVacacional).where(
        PrimaVacacional.estado == PRIMA_PENDIENTE).order_by(PrimaVacacional.id)).all())


def marcar_prima_pagada(session: Session, prima_id: int, *, quien: str,
                        origen: str = "telegram") -> PrimaVacacional:
    """Daniel la pagó (aparte de la nómina semanal). Una sola vez."""
    from pos_uniformes.services.nomina_service import puede_pagar

    if not puede_pagar(quien):
        raise NoSePuede("Solo el dueño o el encargado registran pagos.")
    prima = session.get(PrimaVacacional, int(prima_id))
    if prima is None:
        raise NoSePuede("Esa prima no existe.")
    if prima.estado != PRIMA_PENDIENTE:
        raise NoSePuede(f"Esa prima ya está {prima.estado}.")
    prima.estado = PRIMA_PAGADA
    prima.pagada_at = _ahora()
    prima.pagada_por = _code(quien)
    session.flush()
    _auditar(session, "prima_pagada", prima.employee_code, quien, origen=origen,
             despues={"prima_id": prima.id, "monto": str(prima.monto)})
    return prima


@dataclass
class ConciliacionEmpleada:
    employee_code: str
    dias_vacaciones: list[date]
    faltas_en_vacaciones: list[date]
    primas_pendientes: Decimal
    primas_pagadas: Decimal


def conciliacion_nomina(session: Session, desde: date, hasta: date) -> list[ConciliacionEmpleada]:
    """Lo que la nómina debe reflejar en el rango: días de vacaciones (pagados,
    no faltas), y primas pendientes/pagadas. `faltas_en_vacaciones` debe estar
    vacío: si no, hay un día con dos marcas que revisar."""
    from pos_uniformes.database.models import EmpleadaEvento
    from pos_uniformes.services.calendario_empleadas_service import FALTA, VACACIONES

    por_code: dict[str, ConciliacionEmpleada] = {}

    def _de(code):
        return por_code.setdefault(code, ConciliacionEmpleada(code, [], [], Decimal("0.00"), Decimal("0.00")))

    vac = session.query(EmpleadaEvento).filter(
        EmpleadaEvento.tipo == VACACIONES, EmpleadaEvento.fecha.between(desde, hasta)).all()
    for ev in vac:
        _de(ev.employee_code).dias_vacaciones.append(ev.fecha)
    dias_vac = {(ev.employee_code, ev.fecha) for ev in vac}
    for ev in session.query(EmpleadaEvento).filter(
            EmpleadaEvento.tipo == FALTA, EmpleadaEvento.fecha.between(desde, hasta)).all():
        if (ev.employee_code, ev.fecha) in dias_vac:
            _de(ev.employee_code).faltas_en_vacaciones.append(ev.fecha)
    for prima, s in session.query(PrimaVacacional, SolicitudVacaciones).join(
            SolicitudVacaciones, SolicitudVacaciones.id == PrimaVacacional.solicitud_id).filter(
            SolicitudVacaciones.desde <= hasta, SolicitudVacaciones.hasta >= desde).all():
        c = _de(prima.employee_code)
        if prima.estado == PRIMA_PENDIENTE:
            c.primas_pendientes += prima.monto
        elif prima.estado == PRIMA_PAGADA:
            c.primas_pagadas += prima.monto
    for c in por_code.values():
        c.dias_vacaciones.sort()
    return sorted(por_code.values(), key=lambda c: c.employee_code)


# ── Lo que ella ve de vuelta ─────────────────────────────────────────────────

def respuestas_sin_ver(session: Session, employee_code: str) -> list[SolicitudVacaciones]:
    return list(session.scalars(select(SolicitudVacaciones).where(
        SolicitudVacaciones.employee_code == _code(employee_code),
        SolicitudVacaciones.estado.in_((APROBADO, RECHAZADO, VENCIDO, REVOCADO, CANCELADO)),
        SolicitudVacaciones.avisada_at.is_(None),
    ).order_by(SolicitudVacaciones.id)).all())


def marcar_vista(session: Session, sid: int, employee_code: str) -> None:
    s = session.get(SolicitudVacaciones, int(sid))
    if s is not None and _code(s.employee_code) == _code(employee_code) and s.avisada_at is None:
        s.avisada_at = _ahora()
        session.flush()


def texto_de_respuesta(s: SolicitudVacaciones) -> str:
    rango = f"del {_dd(s.desde)} al {_dd(s.hasta)}"
    texto = {
        APROBADO: f"🏖️ Daniel aprobó tus vacaciones {rango} ({s.dias} días).",
        RECHAZADO: f"✖️ Daniel no aprobó tus vacaciones {rango}.",
        VENCIDO: f"⌛ Tu solicitud de vacaciones {rango} se quedó sin respuesta y venció.",
        REVOCADO: f"↩️ Se deshicieron tus vacaciones {rango}; los días no disfrutados volvieron a tu saldo.",
        CANCELADO: f"↩️ Se cancelaron tus vacaciones {rango}; los días no disfrutados volvieron a tu saldo.",
    }.get(s.estado, f"Tu solicitud {rango} está {s.estado}.")
    if s.respuesta:
        texto += f"\n«{s.respuesta}»"
    return texto


# ── Tarea del bot ────────────────────────────────────────────────────────────

def tarea_periodica(session: Session, *, hoy: date | None = None) -> list[tuple[str, str]]:
    """Genera periodos por aniversario, registra el disfrute de los días que
    ya pasaron y vence lo que nadie contestó. Sin commit."""
    hoy = hoy or date.today()
    avisos: list[tuple[str, str]] = []
    for exp in session.scalars(select(ExpedienteVacacional)).all():
        for p in generar_periodos(session, exp.employee_code, hoy=hoy):
            avisos.append((
                f"🏖️ {exp.employee_code} cumplió {p.anio_servicio} año(s): le tocan "
                f"{p.dias_correspondientes} días de vacaciones (concederlas antes del "
                f"{p.fecha_limite:%d/%m/%Y}, LFT art. 81).", "",
            ))
    consumir(session, hoy=hoy)
    for s in vencer_pendientes(session, hoy=hoy):
        avisos.append((f"⌛ Venció sin respuesta la solicitud de vacaciones de "
                       f"{s.employee_name or s.employee_code}.", ""))
    return avisos


# ── Bitácora ─────────────────────────────────────────────────────────────────

def _auditar(session, operacion, code, quien, *, solicitud=None, antes=None, despues=None,
             motivo=None, origen: str = "admin") -> None:
    from pos_uniformes.services.auditoria_ausencias_service import registrar

    registrar(
        session, actor=quien, origen=origen, operacion=f"vacaciones:{operacion}",
        entidad="solicitud_vacaciones" if solicitud is not None else "expediente_vacacional",
        entidad_id=getattr(solicitud, "id", None), employee_code=code,
        antes=antes, despues=despues, motivo=motivo,
    )
