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
    try:
        from pos_uniformes.services.alertas_service import encolar, texto_alerta_retiro

        encolar(session, texto_alerta_retiro(retiro))
    except Exception:  # noqa: BLE001 — el retiro ya quedó guardado
        pass
    return retiro


def registrar_gasto(session, *, monto, motivo: str, employee_code: str):
    """Un gasto de la tienda apuntado por una empleada (no por el dueño).

    Es el mismo retiro del cajón de siempre —el corte lo cuenta en «Gastos»—,
    pero quien lo apunta no tiene que ser dueño ni encargado: es dinero que ya
    salió, y lo que importa es que quede escrito en el momento, no que alguien
    lo autorice después (Daniel, 2026-10-01: "un gasto relacionado a la
    tienda, no de ellas").

    A Daniel le llega el aviso al instante con el nombre de quien lo apuntó;
    si estuvo mal, se borra con `eliminar_retiro`.
    """
    from pos_uniformes.database.models import CajaRetiro

    code = str(employee_code or "").strip().upper()
    if not code:
        raise PermissionError("Hay que entrar con el gafete para apuntar un gasto.")
    monto = Decimal(str(monto)).quantize(_CENT)
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero.")
    motivo = (motivo or "").strip()[:120]
    if not motivo:
        raise ValueError("Escribe en qué se gastó.")

    retiro = CajaRetiro(
        monto=monto,
        motivo=motivo,
        creado_por=code,
        created_at=datetime.now().astimezone(),
    )
    session.add(retiro)
    session.commit()
    try:
        from pos_uniformes.services.alertas_service import encolar
        from pos_uniformes.services.nombres_empleadas_service import mostrar

        encolar(
            session,
            f"🧾 Gasto de la tienda: ${monto:,.2f} — {motivo}\n"
            f"Lo apuntó {mostrar(code)}. Si estuvo mal, bórralo desde el corte.",
        )
    except Exception:  # noqa: BLE001 — el gasto ya quedó guardado
        pass
    return retiro


def retiros_del_periodo(session, desde: datetime | None, hasta: datetime, *, solo_en_cajon: bool = True) -> list:
    from pos_uniformes.database.models import CajaRetiro

    stmt = select(CajaRetiro).where(CajaRetiro.created_at <= hasta)
    if solo_en_cajon:
        stmt = stmt.where(CajaRetiro.en_cajon.is_(True))
    if desde is not None:
        stmt = stmt.where(CajaRetiro.created_at > desde)
    return list(session.scalars(stmt.order_by(CajaRetiro.id)).all())


def total_retiros(session, desde: datetime | None, hasta: datetime) -> Decimal:
    from pos_uniformes.database.models import CajaRetiro

    stmt = select(func.coalesce(func.sum(CajaRetiro.monto), 0)).where(
        CajaRetiro.created_at <= hasta, CajaRetiro.en_cajon.is_(True)
    )
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
