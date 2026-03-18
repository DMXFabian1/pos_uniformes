"""Helpers visibles para la vista previa de WhatsApp en Configuracion."""

from __future__ import annotations


def build_settings_whatsapp_preview_text(
    template_key: str,
    template_map: dict[str, str],
    default_templates: dict[str, str],
) -> str:
    sample_values = {
        "cliente": "Ana Perez",
        "folio": "APT-20260311-AB12",
        "saldo": "350.00",
        "vencimiento": "Vence hoy",
        "fecha_compromiso": "2026-03-11",
        "codigo_cliente": "CLI-000125",
    }
    template_text = template_map.get(template_key) or default_templates.get(template_key, "")
    rendered = template_text
    for key, value in sample_values.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))
    return rendered
