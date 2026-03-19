"""Mensajes y guardas operativas para usuarios en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsUserFeedbackView:
    title: str
    message: str


def build_settings_user_guard_feedback(
    action_key: str,
    *,
    is_admin: bool,
    has_selection: bool,
) -> SettingsUserFeedbackView | None:
    if action_key == "create_user":
        if is_admin:
            return None
        return SettingsUserFeedbackView(
            title="Sin permisos",
            message="Solo ADMIN puede crear usuarios.",
        )
    if has_selection:
        return None
    return SettingsUserFeedbackView(
        title="Sin seleccion",
        message="Selecciona un usuario en la tabla.",
    )


def build_settings_user_result_feedback(
    action_key: str,
    *,
    username: str,
    role_label: str | None = None,
    status_text: str | None = None,
) -> SettingsUserFeedbackView:
    if action_key == "create_user":
        return SettingsUserFeedbackView(
            title="Usuario creado",
            message=f"Usuario '{username}' creado correctamente.",
        )
    if action_key == "toggle_user":
        return SettingsUserFeedbackView(
            title="Estado actualizado",
            message=f"Usuario '{username}' {status_text} correctamente.",
        )
    if action_key == "change_user_role":
        return SettingsUserFeedbackView(
            title="Rol actualizado",
            message=f"Usuario '{username}' ahora es {role_label}.",
        )
    if action_key == "change_user_password":
        return SettingsUserFeedbackView(
            title="Contrasena actualizada",
            message=f"Contrasena de '{username}' actualizada correctamente.",
        )
    if action_key == "edit_user":
        return SettingsUserFeedbackView(
            title="Usuario actualizado",
            message=f"Usuario '{username}' actualizado correctamente.",
        )
    raise ValueError(f"Accion no soportada: {action_key}")
