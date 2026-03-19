"""Construye vistas imprimibles para tickets y comprobantes de Caja."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.services.sale_ticket_text_service import build_sale_ticket_text
from pos_uniformes.services.layaway_receipt_text_service import build_layaway_receipt_text


@dataclass(frozen=True)
class PrintableDocumentView:
    title: str
    content: str


@dataclass(frozen=True)
class PrintableDocumentSettings:
    business_name: str
    business_phone: str
    business_address: str
    ticket_footer: str
    preferred_printer: str
    ticket_copies: int


def build_sale_ticket_document_view(session, *, sale_id: int) -> PrintableDocumentView:
    load_sale_for_ticket, _, _, load_print_settings_snapshot = _resolve_sale_document_view_dependencies()
    sale = load_sale_for_ticket(session, sale_id)
    settings = _load_print_settings_snapshot(session, default_ticket_footer="Gracias por tu compra.")
    return PrintableDocumentView(
        title=f"Ticket {sale_id}",
        content=build_sale_ticket_text(
            sale=sale,
            business_name=settings.business_name,
            business_phone=settings.business_phone,
            business_address=settings.business_address,
            ticket_footer=settings.ticket_footer,
            preferred_printer=settings.preferred_printer,
            ticket_copies=settings.ticket_copies,
        ),
    )


def build_layaway_receipt_document_view(session, *, layaway_id: int) -> PrintableDocumentView:
    _, load_layaway_for_receipt, _, _ = _resolve_sale_document_view_dependencies()
    layaway = load_layaway_for_receipt(session, layaway_id)
    settings = _load_print_settings_snapshot(session, default_ticket_footer="Gracias por tu preferencia.")
    return PrintableDocumentView(
        title=f"Apartado {layaway_id}",
        content=build_layaway_receipt_text(
            layaway=layaway,
            business_name=settings.business_name,
            business_phone=settings.business_phone,
            business_address=settings.business_address,
            ticket_footer=settings.ticket_footer,
            preferred_printer=settings.preferred_printer,
            ticket_copies=settings.ticket_copies,
        ),
    )


def build_layaway_sale_ticket_document_view(session, *, layaway_id: int) -> PrintableDocumentView:
    _, _, load_sale_for_layaway_ticket, _ = _resolve_sale_document_view_dependencies()
    sale = load_sale_for_layaway_ticket(session, layaway_id)
    settings = _load_print_settings_snapshot(session, default_ticket_footer="Gracias por tu compra.")
    return PrintableDocumentView(
        title=f"Ticket de entrega {layaway_id}",
        content=build_sale_ticket_text(
            sale=sale,
            business_name=settings.business_name,
            business_phone=settings.business_phone,
            business_address=settings.business_address,
            ticket_footer=settings.ticket_footer,
            preferred_printer=settings.preferred_printer,
            ticket_copies=settings.ticket_copies,
        ),
    )


def _load_print_settings_snapshot(
    session,
    *,
    default_ticket_footer: str,
) -> PrintableDocumentSettings:
    _, _, _, load_print_settings_snapshot = _resolve_sale_document_view_dependencies()
    try:
        snapshot = load_print_settings_snapshot(
            session,
            default_ticket_footer=default_ticket_footer,
        )
        return PrintableDocumentSettings(
            business_name=snapshot.business_name,
            business_phone=snapshot.business_phone,
            business_address=snapshot.business_address,
            ticket_footer=snapshot.ticket_footer,
            preferred_printer=snapshot.preferred_printer,
            ticket_copies=snapshot.ticket_copies,
        )
    except Exception:
        return PrintableDocumentSettings(
            business_name="POS Uniformes",
            business_phone="",
            business_address="",
            ticket_footer=default_ticket_footer,
            preferred_printer="",
            ticket_copies=1,
        )


def _resolve_sale_document_view_dependencies():
    from pos_uniformes.services.business_print_settings_service import load_business_print_settings_snapshot
    from pos_uniformes.services.sale_document_service import (
        load_layaway_for_receipt,
        load_sale_for_layaway_ticket,
        load_sale_for_ticket,
    )

    return (
        load_sale_for_ticket,
        load_layaway_for_receipt,
        load_sale_for_layaway_ticket,
        load_business_print_settings_snapshot,
    )
