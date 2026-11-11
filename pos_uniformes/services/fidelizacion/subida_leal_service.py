"""E5-A: subida automática de Maximoda Club a Maximoda Leal (Daniel, 2026-11-10).

Cuando un miembro de Club junta en la Libreta el gasto del año
(`ConfiguracionNegocio.leal_spend_threshold`, $3,000 por omisión, en los
últimos `loyalty_review_window_days` días, 365 por omisión), pasa solo a Leal:
su Club queda `reemplazada` y Leal activa, con su evento cada una.

- Solo sube desde Club. Profesional y Mayorista no bajan ni cambian.
- La venta que cruza el umbral abona con la tasa de Club; las siguientes, con
  la de Leal (el Monedero mira el programa vigente cuando se hizo la venta).
- Nunca tumba la venta: `subir_sin_bloquear` corre en su punto de guardado.
- Si Leal está pausado o cerrado, nadie sube.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import ConfiguracionNegocio, LibretaVenta, Membresia
from pos_uniformes.services.fidelizacion import membresia_service as ms

_logger = logging.getLogger(__name__)

LEAL = "LEAL"
EV_SUBIDA_AUTOMATICA = "subida_automatica"
QUIEN = "automático (gasto del año)"

UMBRAL_POR_OMISION = Decimal("3000.00")
DIAS_POR_OMISION = 365


def reglas(session: Session) -> tuple[Decimal, int]:
    """(gasto mínimo, días hacia atrás) de la configuración del negocio."""
    config = session.scalar(select(ConfiguracionNegocio).limit(1))
    umbral = getattr(config, "leal_spend_threshold", None) or UMBRAL_POR_OMISION
    dias = getattr(config, "loyalty_review_window_days", None) or DIAS_POR_OMISION
    return Decimal(str(umbral)), int(dias)


def gasto_del_periodo(session: Session, cliente_id: int, *, hasta: datetime, dias: int) -> Decimal:
    """Lo que el cliente compró en la Libreta (ventas, sin apartados ni
    abonos) en los `dias` días que terminan en `hasta`."""
    total = session.scalar(
        select(func.coalesce(func.sum(LibretaVenta.monto_total), 0)).where(
            LibretaVenta.cliente_id == int(cliente_id),
            LibretaVenta.tipo == "venta",
            LibretaVenta.created_at > hasta - timedelta(days=dias),
            LibretaVenta.created_at <= hasta,
        )
    )
    return Decimal(str(total or 0)).quantize(Decimal("0.01"))


def subir_si_alcanza(session: Session, cliente_id: int, *, momento: datetime | None = None,
                     employee_code: str | None = None) -> Membresia | None:
    """Pasa al cliente de Club a Leal si ya juntó el gasto del año.

    Devuelve la membresía nueva de Leal, o None si no aplica. No hace commit."""
    momento = momento or datetime.now(timezone.utc)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    activa = ms.estado_de_cliente(session, int(cliente_id)).activa
    if activa is None or activa.programa.clave != ms.CLUB:
        return None
    leal = ms.programa_por_clave(session, LEAL)
    if leal is None or leal.estado != ms.PROGRAMA_ACTIVO:
        return None
    umbral, dias = reglas(session)
    gasto = gasto_del_periodo(session, int(cliente_id), hasta=momento, dias=dias)
    if gasto < umbral:
        return None

    ahora = datetime.now(timezone.utc)
    activa.estado = ms.REEMPLAZADA
    activa.hasta = ahora
    activa.resuelta_por = QUIEN
    activa.resuelta_en = ahora
    session.add(activa)
    session.flush()  # libera el candado de «una activa» antes de activar Leal
    detalle = {"gasto": str(gasto), "umbral": str(umbral), "dias": dias}
    ms._evento(session, activa, ms.EV_REEMPLAZO, antes=ms.ACTIVA, detalle={"por_programa": LEAL, **detalle},
               employee_code=employee_code, quien=QUIEN)
    nueva = Membresia(
        cliente_id=int(cliente_id),
        programa_id=int(leal.id),
        estado=ms.ACTIVA,
        desde=ahora,
        hasta=ms._hasta(leal, ahora),
        propuesta_por_employee_code=employee_code,
        resuelta_por=QUIEN,
        resuelta_en=ahora,
        avisada_at=ahora,  # nadie la propuso: no hay respuesta que avisar
    )
    session.add(nueva)
    session.flush()
    ms._evento(session, nueva, EV_SUBIDA_AUTOMATICA, antes=None, detalle=detalle,
               employee_code=employee_code, quien=QUIEN)
    session.flush()
    _logger.info("Cliente %s sube a Maximoda Leal (gasto %s ≥ %s)", cliente_id, gasto, umbral)
    return nueva


def subir_sin_bloquear(session: Session, venta: LibretaVenta) -> Membresia | None:
    """Después de una venta con cliente: si falla, la venta sigue igual."""
    if venta is None or venta.cliente_id is None or str(venta.tipo) != "venta":
        return None
    try:
        with session.begin_nested():
            return subir_si_alcanza(session, int(venta.cliente_id), momento=venta.created_at,
                                    employee_code=(venta.employee_code or None))
    except Exception:  # noqa: BLE001 - subir de programa nunca tumba la venta
        _logger.exception("No se revisó la subida a Leal del cliente %s", venta.cliente_id)
        return None
