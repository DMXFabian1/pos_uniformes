"""Aviso a Daniel por Telegram de cada venta cobrada con QR de descuento
(2026-11-16).

Usa la misma cola que los cortes y retiros (`alerta_telegram`, ver
`alertas_service`): la venta deja el texto y el bot de la caja lo manda.
Los kioskos no necesitan el token.

El aviso entra en la MISMA transacción que la venta (`registrar_operacion`),
dentro de su propio savepoint: si la venta no se guarda no hay aviso, y si el
aviso falla la venta sigue. Lleva folio, empleada, %, importe descontado y
total cobrado; nunca el código del QR (la venta no lo guarda).
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from pos_uniformes.services.descuento_qr_service import texto_pct

_logger = logging.getLogger(__name__)
_CENT = Decimal("0.01")


def _dinero(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(_CENT)


def qr_de_la_fotografia(foto) -> dict | None:
    """El bloque `descuento_qr` del cálculo (el del servidor primero) con el
    total cobrado, si el QR descontó algo; None si no."""
    if not isinstance(foto, dict):
        return None
    servidor = foto.get("servidor")
    candidatos = [servidor.get("calculo") if isinstance(servidor, dict) else None, foto.get("calculo")]
    for calc in candidatos:
        if not isinstance(calc, dict):
            continue
        qr = calc.get("descuento_qr")
        if not isinstance(qr, dict):
            return None
        try:
            if _dinero(qr.get("importe")) > 0:
                return {**qr, "total": calc.get("total")}
        except ArithmeticError:
            return None
        return None
    return None


def texto_aviso(*, folio: str | None, operacion_id, empleada: str, pct, importe, total) -> str:
    folio_corto = str(folio or "")[:8] or "sin folio"
    return (
        "🏷️ Venta con QR de descuento\n"
        f"Folio {folio_corto} (operación #{operacion_id})\n"
        f"Atendió: {empleada}\n"
        f"Descuento: {texto_pct(pct)} · −${_dinero(importe):,.2f}\n"
        f"Cobrado: ${_dinero(total):,.2f}"
    )


def _empleada(entry) -> str:
    nombre = str(getattr(entry, "employee_name", "") or "").strip()
    codigo = str(getattr(entry, "employee_code", "") or "").strip()
    if codigo and codigo.upper() not in nombre.upper():
        return f"{nombre} ({codigo})" if nombre else codigo
    return nombre or "sin empleada"


def avisar_venta_con_qr(session, entry) -> bool:
    """Deja el aviso en la cola de Telegram si la venta lleva QR. No hace
    commit (lo hace quien guarda la venta). True si quedó en la cola."""
    try:
        qr = qr_de_la_fotografia(getattr(entry, "calculo", None))
        if qr is None:
            return False
        texto = texto_aviso(
            folio=getattr(entry, "operacion_uuid", None),
            operacion_id=getattr(entry, "id", None),
            empleada=_empleada(entry),
            pct=qr.get("pct") or "0",
            importe=qr.get("importe"),
            total=qr.get("total") if qr.get("total") is not None else getattr(entry, "monto_total", 0),
        )
        from pos_uniformes.database.models import AlertaTelegram

        with session.begin_nested():
            session.add(AlertaTelegram(texto=texto, created_at=datetime.now().astimezone()))
            session.flush()
        return True
    except Exception as exc:  # noqa: BLE001 — el aviso nunca tumba la venta
        _logger.warning("QR de descuento: no se pudo encolar el aviso de la venta (%s)", type(exc).__name__)
        return False
