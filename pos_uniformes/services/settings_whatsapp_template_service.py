"""Plantillas reutilizables de WhatsApp para Configuracion y flujos operativos."""

from __future__ import annotations


def build_default_settings_whatsapp_templates() -> dict[str, str]:
    return {
        "layaway_reminder": (
            "Hola {cliente}, te recordamos tu apartado {folio}. "
            "Saldo pendiente: ${saldo}. Estado de vencimiento: {vencimiento}. "
            "Fecha compromiso: {fecha_compromiso}."
        ),
        "layaway_liquidated": (
            "Hola {cliente}, tu apartado {folio} ya esta liquidado y listo para entrega. "
            "Fecha compromiso: {fecha_compromiso}."
        ),
        "client_promotion": (
            "Hola {cliente}, queremos compartirte una promocion especial disponible en tienda."
        ),
        "client_followup": (
            "Hola {cliente}, te escribimos para dar seguimiento y ponernos a tus ordenes."
        ),
        "client_greeting": (
            "Hola {cliente}, gracias por seguir en contacto con nosotros."
        ),
    }


def build_settings_whatsapp_template_map(
    *,
    layaway_reminder: str,
    layaway_liquidated: str,
    client_promotion: str,
    client_followup: str,
    client_greeting: str,
) -> dict[str, str]:
    return {
        "layaway_reminder": layaway_reminder.strip(),
        "layaway_liquidated": layaway_liquidated.strip(),
        "client_promotion": client_promotion.strip(),
        "client_followup": client_followup.strip(),
        "client_greeting": client_greeting.strip(),
    }


def resolve_settings_whatsapp_templates(config, *, default_templates: dict[str, str]) -> dict[str, str]:
    return {
        "layaway_reminder": config.whatsapp_apartado_recordatorio or default_templates["layaway_reminder"],
        "layaway_liquidated": config.whatsapp_apartado_liquidado or default_templates["layaway_liquidated"],
        "client_promotion": config.whatsapp_cliente_promocion or default_templates["client_promotion"],
        "client_followup": config.whatsapp_cliente_seguimiento or default_templates["client_followup"],
        "client_greeting": config.whatsapp_cliente_saludo or default_templates["client_greeting"],
    }


def render_settings_whatsapp_template(template: str, values: dict[str, object]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))
    return rendered
