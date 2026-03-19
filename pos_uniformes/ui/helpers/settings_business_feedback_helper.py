"""Mensajes y guardas para negocio, marketing y WhatsApp en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsBusinessFeedbackView:
    title: str
    message: str


def build_settings_business_guard_feedback(*, is_admin: bool) -> SettingsBusinessFeedbackView | None:
    if is_admin:
        return None
    return SettingsBusinessFeedbackView(
        title="Sin permisos",
        message="Solo ADMIN puede actualizar esta configuracion.",
    )


def build_settings_business_result_feedback(success_message: str) -> SettingsBusinessFeedbackView:
    return SettingsBusinessFeedbackView(
        title="Configuracion guardada",
        message=success_message,
    )
