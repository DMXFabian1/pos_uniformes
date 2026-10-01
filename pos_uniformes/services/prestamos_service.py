"""Préstamos a empleadas: lo pide ella, lo apruebas tú, se descuenta del sueldo.

Daniel, 2026-10-01: *"me gustaría que mis muchachas solicitaran préstamos… y
que se descuente en su sueldo"*. Las tres decisiones que lo definen:

- **Ella pide, tú apruebas.** Mientras no apruebes, no existe para la nómina.
- **Se descuenta completo en el siguiente pago.** Sin abonos ni saldos: un
  préstamo vive poco y se cobra de una vez.
- **El efectivo sale del cajón** y queda anotado solo como retiro, para que el
  corte de esa noche cuadre sin que nadie se acuerde de apuntarlo.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import PrestamoEmpleada

PEDIDO, APROBADO, RECHAZADO, COBRADO = "pedido", "aprobado", "rechazado", "cobrado"

#: Más que esto no se pide sin hablarlo en persona.
TOPE = Decimal("5000.00")


class NoSePuede(ValueError):
    pass


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def pedir(session: Session, *, employee_code: str, nombre: str, monto, motivo: str) -> PrestamoEmpleada:
    """La empleada lo pide desde la Libreta. Queda esperando tu respuesta."""
    monto = Decimal(str(monto))
    if monto <= 0:
        raise NoSePuede("El préstamo tiene que ser mayor a cero.")
    if monto > TOPE:
        raise NoSePuede(f"Más de ${TOPE:,.0f} hay que hablarlo con Daniel en persona.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise NoSePuede("Escribe para qué es: sin motivo no se puede autorizar.")

    if pendiente_de(session, employee_code) is not None:
        raise NoSePuede("Ya tienes un préstamo esperando respuesta.")
    if por_cobrar(session, employee_code):
        raise NoSePuede("Ya tienes un préstamo que se te va a descontar en el siguiente pago.")

    prestamo = PrestamoEmpleada(
        employee_code=str(employee_code), employee_name=str(nombre or ""),
        monto=monto, motivo=motivo, estado=PEDIDO,
    )
    session.add(prestamo)
    session.flush()
    return prestamo


def pendiente_de(session: Session, employee_code: str) -> PrestamoEmpleada | None:
    """Su solicitud sin responder, si tiene una."""
    return session.scalars(
        select(PrestamoEmpleada).where(
            PrestamoEmpleada.employee_code == str(employee_code),
            PrestamoEmpleada.estado == PEDIDO,
        ).order_by(PrestamoEmpleada.id)
    ).first()


def pendientes(session: Session) -> list[PrestamoEmpleada]:
    """Todo lo que está esperando tu respuesta, del más viejo al más nuevo."""
    return list(session.scalars(
        select(PrestamoEmpleada)
        .where(PrestamoEmpleada.estado == PEDIDO)
        .order_by(PrestamoEmpleada.id)
    ).all())


def por_cobrar(session: Session, employee_code: str) -> list[PrestamoEmpleada]:
    """Lo aprobado que todavía no se le descuenta."""
    return list(session.scalars(
        select(PrestamoEmpleada).where(
            PrestamoEmpleada.employee_code == str(employee_code),
            PrestamoEmpleada.estado == APROBADO,
        ).order_by(PrestamoEmpleada.id)
    ).all())


def total_por_cobrar(session: Session, employee_code: str) -> Decimal:
    """Cuánto se le descuenta en el siguiente pago.

    Si la base todavía no tiene la tabla (un kiosko que abrió antes de que
    corriera la migración), se devuelve cero: se le paga completo y el
    préstamo sigue esperando. Pagar de más se corrige; no poder pagar, no."""
    try:
        prestamos = por_cobrar(session, employee_code)
    except Exception:  # noqa: BLE001 — base sin la tabla todavía
        session.rollback()
        return Decimal("0.00")
    return sum((Decimal(str(p.monto)) for p in prestamos), Decimal("0.00"))


def aprobar(session: Session, prestamo_id: int, *, quien: str) -> PrestamoEmpleada:
    """Lo autorizas: el dinero sale del cajón y queda anotado como retiro.

    Sin ese retiro, el corte de la noche saldría corto justo por el préstamo y
    parecería un descuadre."""
    prestamo = _pedido(session, prestamo_id)
    prestamo.estado = APROBADO
    prestamo.resuelto_por = str(quien)
    prestamo.resuelto_at = _ahora()
    session.add(prestamo)

    from pos_uniformes.services.retiros_service import registrar_retiro

    registrar_retiro(
        session,
        monto=Decimal(str(prestamo.monto)),
        motivo=f"Préstamo a {prestamo.employee_name or prestamo.employee_code}",
        creado_por=str(quien),
    )
    session.flush()
    return prestamo


def rechazar(session: Session, prestamo_id: int, *, quien: str) -> PrestamoEmpleada:
    prestamo = _pedido(session, prestamo_id)
    prestamo.estado = RECHAZADO
    prestamo.resuelto_por = str(quien)
    prestamo.resuelto_at = _ahora()
    session.add(prestamo)
    session.flush()
    return prestamo


def marcar_cobrados(session: Session, employee_code: str, *, pago_id: int | None = None) -> Decimal:
    """Al pagarle, los préstamos aprobados quedan saldados. Devuelve cuánto."""
    total = Decimal("0.00")
    for p in por_cobrar(session, employee_code):
        p.estado = COBRADO
        p.cobrado_at = _ahora()
        p.pago_id = pago_id
        session.add(p)
        total += Decimal(str(p.monto))
    session.flush()
    return total


def _pedido(session: Session, prestamo_id: int) -> PrestamoEmpleada:
    prestamo = session.get(PrestamoEmpleada, int(prestamo_id))
    if prestamo is None:
        raise NoSePuede("Ese préstamo ya no existe.")
    if prestamo.estado != PEDIDO:
        raise NoSePuede(f"Ese préstamo ya está {prestamo.estado}.")
    return prestamo
