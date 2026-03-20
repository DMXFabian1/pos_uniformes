"""Construye vistas imprimibles para presupuestos."""

from __future__ import annotations

from pos_uniformes.services.quote_text_service import build_quote_text
from pos_uniformes.services.sale_document_view_service import PrintableDocumentView


def build_quote_document_view(session, *, quote_id: int) -> PrintableDocumentView:
    presupuesto_service, load_print_settings_snapshot = _resolve_quote_document_view_dependencies()
    quote = presupuesto_service.obtener_presupuesto(session, quote_id)
    if quote is None:
        raise ValueError("No se encontro el presupuesto seleccionado.")

    settings = load_print_settings_snapshot(
        session,
        default_ticket_footer="Gracias por tu preferencia.",
    )
    return PrintableDocumentView(
        title=f"Presupuesto {quote.folio}",
        content=build_quote_text(
            quote=quote,
            business_name=settings.business_name,
            business_phone=settings.business_phone,
            business_address=settings.business_address,
            ticket_footer=settings.ticket_footer,
        ),
    )


def _resolve_quote_document_view_dependencies():
    from pos_uniformes.services.business_print_settings_service import load_business_print_settings_snapshot
    from pos_uniformes.services.presupuesto_service import PresupuestoService

    return PresupuestoService, load_business_print_settings_snapshot
