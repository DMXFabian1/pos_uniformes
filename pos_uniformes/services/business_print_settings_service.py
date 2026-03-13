"""Helpers para cargar configuracion operativa de tickets e impresion."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.services.business_settings_service import BusinessSettingsService


@dataclass(frozen=True)
class BusinessPrintSettingsSnapshot:
    business_name: str
    business_phone: str
    business_address: str
    ticket_footer: str
    preferred_printer: str
    ticket_copies: int


def load_business_print_settings_snapshot(
    session,
    *,
    default_business_name: str = "POS Uniformes",
    default_ticket_footer: str = "Gracias por tu compra.",
) -> BusinessPrintSettingsSnapshot:
    config = BusinessSettingsService.get_or_create(session)
    return BusinessPrintSettingsSnapshot(
        business_name=config.nombre_negocio or default_business_name,
        business_phone=config.telefono or "",
        business_address=config.direccion or "",
        ticket_footer=config.pie_ticket or default_ticket_footer,
        preferred_printer=config.impresora_preferida or "",
        ticket_copies=config.copias_ticket or 1,
    )
