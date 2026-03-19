"""Carga el snapshot del detalle seleccionado en Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class QuoteDetailLineSnapshot:
    sku: str
    description: str
    quantity: int
    unit_price: object
    subtotal: object


@dataclass(frozen=True)
class QuoteDetailSnapshot:
    customer_label: str
    phone_text: str
    status_label: str
    total: Decimal
    validity_label: str
    user_label: str
    notes_text: str
    detail_rows: tuple[QuoteDetailLineSnapshot, ...]
    folio: str


def load_quote_detail_snapshot(session, *, quote_id: int) -> QuoteDetailSnapshot:
    presupuesto_service = _resolve_quote_detail_dependencies()
    quote = presupuesto_service.obtener_presupuesto(session, quote_id)
    if quote is None:
        raise ValueError("Presupuesto no encontrado.")
    client_text = quote.cliente_nombre or (quote.cliente.nombre if quote.cliente else "Mostrador / sin cliente")
    phone_text = quote.cliente_telefono or (quote.cliente.telefono if quote.cliente else "Sin telefono")
    return QuoteDetailSnapshot(
        folio=str(quote.folio),
        customer_label=str(client_text),
        phone_text=str(phone_text),
        status_label=str(quote.estado.value),
        total=Decimal(quote.total),
        validity_label=quote.vigencia_hasta.strftime("%Y-%m-%d") if quote.vigencia_hasta else "Sin vigencia",
        user_label=str(quote.usuario.username if quote.usuario else "-"),
        notes_text=str(quote.observacion or "Sin observaciones."),
        detail_rows=tuple(
            QuoteDetailLineSnapshot(
                sku=str(detail.sku_snapshot),
                description=str(detail.descripcion_snapshot),
                quantity=int(detail.cantidad),
                unit_price=detail.precio_unitario,
                subtotal=detail.subtotal_linea,
            )
            for detail in quote.detalles
        ),
    )


def _resolve_quote_detail_dependencies():
    from pos_uniformes.services.presupuesto_service import PresupuestoService

    return PresupuestoService
