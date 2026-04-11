"""Mensajes visibles al crear clientes desde Presupuestos."""

from __future__ import annotations

from pos_uniformes.services.business_settings_service import BusinessSettingsService
from pos_uniformes.services.settings_whatsapp_template_service import (
    build_default_settings_whatsapp_templates,
    render_settings_whatsapp_template,
    resolve_settings_whatsapp_templates,
)


def build_quote_client_created_feedback(session, *, client_name: str, client_code: str) -> str:
    normalized_name = str(client_name or "").strip() or "Cliente nuevo"
    normalized_code = str(client_code or "").strip() or "-"
    config = BusinessSettingsService.get_or_create(session)
    templates = resolve_settings_whatsapp_templates(
        config,
        default_templates=build_default_settings_whatsapp_templates(),
    )
    promotion_message = render_settings_whatsapp_template(
        templates["client_promotion"],
        {
            "cliente": normalized_name,
            "codigo_cliente": normalized_code,
        },
    ).strip()
    return (
        f"Cliente '{normalized_name}' asignado al presupuesto.\n"
        f"Codigo: {normalized_code}\n\n"
        f"Promocion sugerida:\n{promotion_message}"
    )
