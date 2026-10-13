"""Bitácora de ausencias: quién movió qué descanso, cuándo, desde dónde y qué había.

Solo se agrega: nunca se edita ni se borra una fila. No hace commit — entra en
la misma transacción que la operación que registra, así que si la operación se
deshace, su renglón de bitácora también (no queda constancia de algo que no
pasó, ni pasa algo sin constancia).

Guarda códigos de gafete, fechas y estados; nada de datos personales.
"""

from __future__ import annotations

from datetime import datetime

#: De dónde viene la operación.
ORIGENES = ("kiosko", "calendario", "telegram", "movil", "admin", "sistema")


def registrar(
    session,
    *,
    actor: str | None,
    origen: str,
    operacion: str,
    entidad: str,
    entidad_id: int | None = None,
    solicitud_id: int | None = None,
    employee_code: str | None = None,
    antes: dict | None = None,
    despues: dict | None = None,
    motivo: str | None = None,
) -> None:
    from pos_uniformes.database.models import AuditoriaAusencias

    origen = origen if origen in ORIGENES else "admin"
    session.add(AuditoriaAusencias(
        created_at=datetime.now().astimezone(),
        actor=str(actor or "sistema").strip().upper()[:40],
        origen=origen,
        operacion=operacion[:40],
        entidad=entidad[:40],
        entidad_id=entidad_id,
        solicitud_id=solicitud_id,
        employee_code=(str(employee_code).strip().upper()[:40] if employee_code else None),
        antes=antes,
        despues=despues,
        motivo=(str(motivo)[:200] if motivo else None),
    ))


def historial(session, *, employee_code: str | None = None, solicitud_id: int | None = None) -> list:
    from pos_uniformes.database.models import AuditoriaAusencias

    q = session.query(AuditoriaAusencias)
    if employee_code:
        q = q.filter(AuditoriaAusencias.employee_code == str(employee_code).strip().upper())
    if solicitud_id is not None:
        q = q.filter(AuditoriaAusencias.solicitud_id == solicitud_id)
    return q.order_by(AuditoriaAusencias.id).all()
