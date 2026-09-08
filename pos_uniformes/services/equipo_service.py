"""Alta y baja de empleadas por temporada (desde la Libreta del dueño).

Dar de baja = `activo = False`. No se borra nada: la Libreta, los pagos y el
calendario quedan; la empleada deja de aparecer en pendientes, avisos de
pago, ranking y ya no puede entrar con su gafete. Reactivar la regresa.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

CODIGOS_GESTION = ("VEND-1", "ENC-1")


@dataclass(frozen=True)
class FichaEmpleada:
    codigo: str
    nombre: str
    activa: bool
    descanso: str  # "descansa lunes", "trabaja sáb, dom" o "sin configurar"
    ultimo_pago: date | None
    ultimo_movimiento: date | None
    modo_pago: str = "semana"


def listar_equipo(session) -> list[FichaEmpleada]:
    """Todas las empleadas (activas primero), sin el dueño ni el encargado."""
    from sqlalchemy import func

    from pos_uniformes.database.models import Empleada, EmpleadaHorario, LibretaVenta
    from pos_uniformes.services.calendario_empleadas_service import MODO_POR_DIA, WEEKDAY_NAMES

    horarios = {h.employee_code.upper(): h for h in session.scalars(select(EmpleadaHorario)).all()}
    ultimos = {
        str(code).upper(): fecha
        for code, fecha in session.execute(
            select(LibretaVenta.employee_code, func.max(LibretaVenta.created_at)).group_by(LibretaVenta.employee_code)
        ).all()
    }
    fichas = []
    for e in session.scalars(select(Empleada).order_by(Empleada.nombre_completo)).all():
        code = str(e.codigo).upper()
        if code in CODIGOS_GESTION:
            continue
        h = horarios.get(code)
        descanso = "sin configurar"
        modo = (getattr(h, "modo_pago", None) or "semana") if h is not None else "semana"
        if h is not None and modo == MODO_POR_DIA:
            dias = sorted({int(d) for d in (h.dias_trabajo or [])})
            cortos = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
            descanso = ("trabaja " + ", ".join(cortos[d] for d in dias if 0 <= d <= 6)) if dias else "sin configurar"
        elif h is not None and h.descanso_weekday is not None:
            descanso = "descansa " + WEEKDAY_NAMES[h.descanso_weekday]
        ult = ultimos.get(code)
        if ult is not None and ult.tzinfo is not None:
            ult = ult.astimezone()
        fichas.append(
            FichaEmpleada(
                codigo=code,
                nombre=e.nombre_completo,
                activa=bool(e.activo),
                descanso=descanso,
                modo_pago=modo,
                ultimo_pago=h.fecha_ultimo_pago if h is not None else None,
                ultimo_movimiento=ult.date() if ult is not None else None,
            )
        )
    fichas.sort(key=lambda f: (not f.activa, f.nombre))
    return fichas


def cambiar_estado(session, codigo: str, *, activa: bool):
    """Activa o da de baja. Devuelve la Empleada. Lanza ValueError si no existe
    o si es el dueño/encargado."""
    from pos_uniformes.database.models import Empleada

    code = str(codigo).strip().upper()
    if code in CODIGOS_GESTION:
        raise ValueError("Ese gafete no se puede dar de baja desde aquí.")
    emp = session.scalar(select(Empleada).where(Empleada.codigo == code))
    if emp is None:
        raise ValueError(f"No existe la empleada {code}.")
    emp.activo = bool(activa)
    session.commit()
    return emp
