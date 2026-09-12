"""Lista de asistencia del equipo, para el bot de Telegram.

Nadie checa entrada: la presencia se **deduce** del primer movimiento del día
en la Libreta (una venta, un apartado, un abono) o de una jornada de conteo
abierta. Por eso el mensaje distingue "vino" de "sin señal todavía": una
empleada puede estar en el piso y no haber vendido aún.

Lo que sí es dato duro: el descanso (fijo o marcado) y la falta que marcó
León o Daniel en el calendario.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

PRESENTE = "presente"
SIN_SENAL = "sin_senal"
DESCANSO = "descanso"
FALTA = "falta"

_ICONO = {PRESENTE: "✅", SIN_SENAL: "⏳", DESCANSO: "🛌", FALTA: "✗"}
_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


@dataclass(frozen=True)
class Asistencia:
    code: str
    nombre: str
    estado: str
    primera_senal: datetime | None = None   # hora local del primer movimiento
    movimientos: int = 0
    nota: str = ""                          # p.ej. "marcada por León"

    @property
    def nombre_corto(self) -> str:
        return self.nombre.split()[0] if self.nombre else self.code


def _local(momento: datetime) -> datetime:
    """Postgres devuelve con zona → a hora local. SQLite (tests) devuelve sin
    zona y ya es hora local: se deja como está (igual que analitica_libreta)."""
    if momento.tzinfo is None:
        return momento
    return momento.astimezone().replace(tzinfo=None)


def clasificar(*, estado_dia: str, movimientos: int, primera: datetime | None) -> str:
    """Puro: del estado del calendario y la actividad, el estado de asistencia."""
    from pos_uniformes.services.calendario_empleadas_service import DESCANSO as C_DESCANSO
    from pos_uniformes.services.calendario_empleadas_service import FALTA as C_FALTA

    if estado_dia == C_FALTA:
        return FALTA
    if estado_dia == C_DESCANSO:
        return DESCANSO
    return PRESENTE if (movimientos > 0 or primera is not None) else SIN_SENAL


def asistencia_del_dia(session, hoy: date | None = None) -> list[Asistencia]:
    from sqlalchemy import func, select

    from pos_uniformes.database.models import ConteoJornada, Empleada, LibretaVenta
    from pos_uniformes.services.calendario_empleadas_service import cargar_horario, estado_del_dia
    from pos_uniformes.services.libreta_service import ventana_hoy
    from pos_uniformes.services.nomina_service import QUIEN_PUEDE_PAGAR

    hoy = hoy or date.today()
    desde, hasta = ventana_hoy(hoy)

    empleadas = [
        e for e in session.scalars(
            select(Empleada).where(Empleada.activo.is_(True)).order_by(Empleada.nombre_completo)
        ).all()
        if e.codigo.upper() not in QUIEN_PUEDE_PAGAR
    ]

    # Primer movimiento y cuántos, por empleada, en la Libreta de hoy.
    filas = session.execute(
        select(LibretaVenta.employee_code, func.min(LibretaVenta.created_at), func.count())
        .where(LibretaVenta.created_at >= desde, LibretaVenta.created_at <= hasta)
        .group_by(LibretaVenta.employee_code)
    ).all()
    actividad = {str(c).upper(): (_local(m), int(n)) for c, m, n in filas if c}

    # Una jornada de conteo abierta hoy también es presencia.
    try:
        jornadas = session.execute(
            select(ConteoJornada.empleada_code, func.min(ConteoJornada.iniciada_at))
            .where(ConteoJornada.iniciada_at >= desde, ConteoJornada.iniciada_at <= hasta)
            .group_by(ConteoJornada.empleada_code)
        ).all()
    except Exception:  # noqa: BLE001 — base sin la tabla todavía
        session.rollback()
        jornadas = []
    for c, m in jornadas:
        code = str(c).upper()
        primera, n = actividad.get(code, (None, 0))
        m_local = _local(m)
        actividad[code] = (m_local if primera is None or m_local < primera else primera, n)

    salida: list[Asistencia] = []
    for e in empleadas:
        code = e.codigo.upper()
        horario = cargar_horario(session, e.codigo)
        estado_dia = estado_del_dia(horario, hoy)
        primera, n = actividad.get(code, (None, 0))
        estado = clasificar(estado_dia=estado_dia, movimientos=n, primera=primera)
        nota = ""
        if estado in (FALTA, DESCANSO) and hoy in horario.eventos:
            nota = "marcado en el calendario"
        salida.append(Asistencia(code, e.nombre_completo, estado, primera, n, nota))
    orden = {PRESENTE: 0, SIN_SENAL: 1, FALTA: 2, DESCANSO: 3}
    return sorted(salida, key=lambda a: (orden[a.estado], a.primera_senal or datetime.max, a.nombre))


def texto_asistencia(lista: list[Asistencia], hoy: date | None = None, ahora: datetime | None = None) -> str:
    """El mensaje, puro."""
    hoy = hoy or date.today()
    ahora = ahora or datetime.now()
    lineas = [f"👥 Asistencia · {_DIAS[hoy.weekday()]} {hoy:%d/%m} · {ahora:%H:%M}"]
    if not lista:
        lineas.append("No hay empleadas activas.")
        return "\n".join(lineas)
    for a in lista:
        icono = _ICONO[a.estado]
        if a.estado == PRESENTE:
            hora = f" desde {a.primera_senal:%H:%M}" if a.primera_senal else ""
            movs = f" · {a.movimientos} mov." if a.movimientos else ""
            lineas.append(f"{icono} {a.nombre_corto} —{hora}{movs}")
        elif a.estado == SIN_SENAL:
            lineas.append(f"{icono} {a.nombre_corto} — sin movimientos todavía")
        elif a.estado == FALTA:
            lineas.append(f"{icono} {a.nombre_corto} — falta" + (f" ({a.nota})" if a.nota else ""))
        else:
            lineas.append(f"{icono} {a.nombre_corto} — descansa")
    cuenta = {k: sum(1 for a in lista if a.estado == k) for k in (PRESENTE, SIN_SENAL, DESCANSO, FALTA)}
    partes = [f"{cuenta[PRESENTE]} presentes"]
    if cuenta[SIN_SENAL]:
        partes.append(f"{cuenta[SIN_SENAL]} sin señal")
    if cuenta[DESCANSO]:
        partes.append(f"{cuenta[DESCANSO]} descanso")
    if cuenta[FALTA]:
        partes.append(f"{cuenta[FALTA]} falta")
    lineas.append("—")
    lineas.append(f"{len(lista)} activas · " + " · ".join(partes))
    lineas.append("Presencia = primer movimiento en la Libreta o un conteo abierto.")
    return "\n".join(lineas)
