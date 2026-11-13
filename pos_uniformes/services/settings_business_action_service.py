"""Carga y guardado operativo de negocio, marketing y WhatsApp en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsBusinessFormSnapshot:
    business_name: str
    logo_path: str
    loyalty_review_window_days: int
    leal_spend_threshold: float
    phone: str
    address: str
    footer: str
    transfer_bank: str
    transfer_beneficiary: str
    transfer_clabe: str
    transfer_instructions: str
    whatsapp_layaway_reminder: str
    whatsapp_layaway_liquidated: str
    whatsapp_client_promotion: str
    whatsapp_client_followup: str
    whatsapp_client_greeting: str
    preferred_printer: str
    ticket_printer: str
    ticket_copies: int


def load_settings_business_form_snapshot(session, *, default_templates: dict[str, str]) -> SettingsBusinessFormSnapshot:
    business_settings_service, whatsapp_template_service = _resolve_settings_business_form_dependencies()
    config = business_settings_service.get_or_create(session)
    whatsapp_templates = whatsapp_template_service.resolve_settings_whatsapp_templates(
        config,
        default_templates=default_templates,
    )
    return SettingsBusinessFormSnapshot(
        business_name=str(config.nombre_negocio or ""),
        logo_path=str(config.logo_path or ""),
        loyalty_review_window_days=int(config.loyalty_review_window_days or 365),
        leal_spend_threshold=float(config.leal_spend_threshold or 3000),
        # 2026-11-12: sin los campos del nivel viejo («el nivel viejo
        # retíralo», Daniel): compras mínimas, monto por frecuencia y
        # descuentos por nivel.
        phone=str(config.telefono or ""),
        address=str(config.direccion or ""),
        footer=str(config.pie_ticket or ""),
        transfer_bank=str(config.transferencia_banco or ""),
        transfer_beneficiary=str(config.transferencia_beneficiario or ""),
        transfer_clabe=str(config.transferencia_clabe or ""),
        transfer_instructions=str(config.transferencia_instrucciones or ""),
        whatsapp_layaway_reminder=whatsapp_templates["layaway_reminder"],
        whatsapp_layaway_liquidated=whatsapp_templates["layaway_liquidated"],
        whatsapp_client_promotion=whatsapp_templates["client_promotion"],
        whatsapp_client_followup=whatsapp_templates["client_followup"],
        whatsapp_client_greeting=whatsapp_templates["client_greeting"],
        preferred_printer=str(config.impresora_preferida or ""),
        ticket_printer=str(config.impresora_tickets or ""),
        ticket_copies=int(config.copias_ticket or 1),
    )


def save_settings_business_payload(session, *, admin_user_id: int, payload) -> None:
    business_settings_service, usuario_model = _resolve_settings_business_action_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    if admin_user is None:
        raise ValueError("Administrador no encontrado.")
    business_settings_service.update_settings(
        session=session,
        admin_user=admin_user,
        payload=payload,
    )


def _resolve_settings_business_form_dependencies():
    from pos_uniformes.services.business_settings_service import BusinessSettingsService
    from pos_uniformes.services import settings_whatsapp_template_service

    return BusinessSettingsService, settings_whatsapp_template_service


def _resolve_settings_business_action_dependencies():
    from pos_uniformes.database.models import Usuario
    from pos_uniformes.services.business_settings_service import BusinessSettingsService

    return BusinessSettingsService, Usuario
