"""Retiros del cajón con motivo (lo que no es pago a empleada).

Solo el dueño (VEND-1) y el encargado (ENC-1). Se fechan al momento; el
corte del periodo los descuenta del esperado y el ticket los lista.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

MOTIVOS_RAPIDOS = ("Proveedor", "Renta", "Cambio", "Comida", "Luz / agua", "Otro")
_CENT = Decimal("0.01")


def registrar_retiro(session, *, monto, motivo: str, creado_por: str):
    from pos_uniformes.database.models import CajaRetiro
    from pos_uniformes.services.nomina_service import puede_pagar

    if not puede_pagar(creado_por):
        raise PermissionError("Solo el dueño o el encargado apuntan retiros.")
    monto = Decimal(str(monto)).quantize(_CENT)
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero.")
    motivo = (motivo or "").strip()[:120]
    if not motivo:
        raise ValueError("Escribe para qué fue el dinero.")
    retiro = CajaRetiro(
        monto=monto,
        motivo=motivo,
        creado_por=str(creado_por).strip().upper(),
        created_at=datetime.now().astimezone(),
    )
    session.add(retiro)
    session.commit()
    return retiro


def retiros_del_periodo(session, desde: datetime | None, hasta: datetime) -> list:
    from pos_uniformes.database.models import CajaRetiro

    stmt = select(CajaRetiro).where(CajaRetiro.created_at <= hasta)
    if desde is not None:
        stmt = stmt.where(CajaRetiro.created_at > desde)
    return list(session.scalars(stmt.order_by(CajaRetiro.id)).all())


def total_retiros(session, desde: datetime | None, hasta: datetime) -> Decimal:
    from pos_uniformes.database.models import CajaRetiro

    stmt = select(func.coalesce(func.sum(CajaRetiro.monto), 0)).where(CajaRetiro.created_at <= hasta)
    if desde is not None:
        stmt = stmt.where(CajaRetiro.created_at > desde)
    return Decimal(str(session.scalar(stmt) or 0)).quantize(_CENT)


def eliminar_retiro(session, retiro_id: int, *, creado_por: str) -> bool:
    """Para el "me equivoqué": borra un retiro recién apuntado."""
    from pos_uniformes.database.models import CajaRetiro
    from pos_uniformes.services.nomina_service import puede_pagar

    if not puede_pagar(creado_por):
        raise PermissionError("Solo el dueño o el encargado.")
    retiro = session.get(CajaRetiro, int(retiro_id))
    if retiro is None:
        return False
    session.delete(retiro)
    session.commit()
    return True
