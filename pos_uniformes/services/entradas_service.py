"""Entradas al cajón que no son venta (el fondo del papá de Daniel).

Espejo de `retiros_service`: solo el dueño (VEND-1) y el encargado (ENC-1),
se fechan al momento (o a la hora del corte si se apuntan desde ahí), el
corte del periodo las SUMA al esperado y el ticket las lista. Los pagos a
empleadas siguen saliendo del cajón completos: lo que entró los cubre, y lo
que sobre se queda como dinero del cajón (Daniel, 2026-10-20).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

MOTIVO_POR_DEFECTO = "Fondo de papá"
_CENT = Decimal("0.01")


def registrar_entrada(session, *, monto, motivo: str, creado_por: str, momento: datetime | None = None):
    from pos_uniformes.database.models import CajaEntrada
    from pos_uniformes.services.nomina_service import puede_pagar

    if not puede_pagar(creado_por):
        raise PermissionError("Solo el dueño o el encargado apuntan entradas al cajón.")
    monto = Decimal(str(monto)).quantize(_CENT)
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero.")
    motivo = (motivo or "").strip()[:120] or MOTIVO_POR_DEFECTO
    ahora = momento or datetime.now().astimezone()
    # La misma entrada dos veces en dos minutos es un doble envío, no dos
    # entradas (misma red que los retiros).
    repetida = session.scalars(
        select(CajaEntrada).where(
            CajaEntrada.monto == monto,
            CajaEntrada.motivo == motivo,
            CajaEntrada.created_at >= ahora - timedelta(minutes=2),
        ).limit(1)
    ).first()
    if repetida is not None:
        raise ValueError(
            f"Esa entrada (${monto:,.2f}, {motivo}) ya quedó apuntada hace un momento. "
            "Si de verdad son dos, espera dos minutos o cambia el motivo."
        )
    entrada = CajaEntrada(monto=monto, motivo=motivo, creado_por=str(creado_por).strip().upper(), created_at=ahora)
    session.add(entrada)
    session.commit()
    try:
        from pos_uniformes.services.alertas_service import encolar

        encolar(session, texto_alerta_entrada(entrada))
    except Exception:  # noqa: BLE001 — la entrada ya quedó guardada
        pass
    return entrada


def texto_alerta_entrada(entrada) -> str:
    try:
        hora = entrada.created_at.astimezone().strftime("%H:%M")
    except Exception:  # noqa: BLE001
        hora = ""
    return (f"➕ Entró al cajón (no venta): ${Decimal(entrada.monto):,.2f} — {entrada.motivo} "
            f"({str(entrada.creado_por).upper()}, {hora})")


def entradas_del_periodo(session, desde: datetime | None, hasta: datetime) -> list:
    from pos_uniformes.database.models import CajaEntrada

    stmt = select(CajaEntrada).where(CajaEntrada.created_at <= hasta)
    if desde is not None:
        stmt = stmt.where(CajaEntrada.created_at > desde)
    return list(session.scalars(stmt.order_by(CajaEntrada.id)).all())


def total_entradas(session, desde: datetime | None, hasta: datetime) -> Decimal:
    from pos_uniformes.database.models import CajaEntrada

    stmt = select(func.coalesce(func.sum(CajaEntrada.monto), 0)).where(CajaEntrada.created_at <= hasta)
    if desde is not None:
        stmt = stmt.where(CajaEntrada.created_at > desde)
    return Decimal(str(session.scalar(stmt) or 0)).quantize(_CENT)


def eliminar_entrada(session, entrada_id: int, *, creado_por: str) -> bool:
    """Para el «me equivoqué»: borra una entrada recién apuntada."""
    from pos_uniformes.database.models import CajaEntrada
    from pos_uniformes.services.nomina_service import puede_pagar

    if not puede_pagar(creado_por):
        raise PermissionError("Solo el dueño o el encargado.")
    entrada = session.get(CajaEntrada, int(entrada_id))
    if entrada is None:
        return False
    session.delete(entrada)
    session.commit()
    return True
