"""Mensaje reusable para compartir presupuestos por WhatsApp."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class QuoteWhatsappView:
    phone_number: str
    customer_label: str
    message: str


def build_quote_whatsapp_view(session, *, quote_id: int) -> QuoteWhatsappView:
    presupuesto_service, load_print_settings_snapshot = _resolve_quote_whatsapp_dependencies()
    quote = presupuesto_service.obtener_presupuesto(session, quote_id)
    if quote is None:
        raise ValueError("No se encontro el presupuesto seleccionado.")

    phone_number = str(quote.cliente_telefono or (quote.cliente.telefono if quote.cliente else "")).strip()
    if not phone_number:
        raise ValueError("El presupuesto seleccionado no tiene telefono para WhatsApp.")

    settings = load_print_settings_snapshot(
        session,
        default_ticket_footer="Gracias por tu preferencia.",
    )
    customer_label = str(quote.cliente_nombre or (quote.cliente.nombre if quote.cliente else "cliente"))
    return QuoteWhatsappView(
        phone_number=phone_number,
        customer_label=customer_label,
        message=_build_quote_whatsapp_message(
            quote=quote,
            business_name=settings.business_name,
        ),
    )


def _build_quote_whatsapp_message(*, quote, business_name: str) -> str:
    customer_label = quote.cliente_nombre or (quote.cliente.nombre if quote.cliente else "cliente")
    lines = [
        f"Hola {customer_label}, te compartimos tu presupuesto {quote.folio} de {business_name}.",
        f"Estado: {quote.estado.value}",
        f"Total estimado: ${Decimal(quote.total).quantize(Decimal('0.01'))}",
    ]
    if quote.vigencia_hasta is not None:
        lines.append(f"Vigencia: {quote.vigencia_hasta.strftime('%Y-%m-%d')}")
    lines.append("Piezas:")
    for detail in quote.detalles:
        subtotal = Decimal(detail.subtotal_linea).quantize(Decimal("0.01"))
        lines.append(f"- {detail.descripcion_snapshot} | {detail.cantidad} pza(s) | ${subtotal}")
    if quote.observacion:
        lines.append(f"Observaciones: {quote.observacion}")
    lines.append("Si deseas retomarlo, responde con tu folio o este mismo mensaje.")
    return "\n".join(lines)


def _resolve_quote_whatsapp_dependencies():
    from pos_uniformes.services.business_print_settings_service import load_business_print_settings_snapshot
    from pos_uniformes.services.presupuesto_service import PresupuestoService

    return PresupuestoService, load_business_print_settings_snapshot
