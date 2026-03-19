"""Mutaciones operativas para usuarios desde Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsUserPromptSnapshot:
    username: str
    full_name: str
    current_role: object


@dataclass(frozen=True)
class SettingsUserActionResult:
    username: str
    role_label: str | None = None
    status_text: str | None = None


def load_settings_user_prompt_snapshot(session, *, user_id: int) -> SettingsUserPromptSnapshot:
    usuario_model = _resolve_settings_user_model()
    target_user = session.get(usuario_model, user_id)
    if target_user is None:
        raise ValueError("No se encontro el usuario seleccionado.")
    return SettingsUserPromptSnapshot(
        username=str(target_user.username),
        full_name=str(target_user.nombre_completo),
        current_role=target_user.rol,
    )


def create_settings_user(session, *, admin_user_id: int, payload: dict[str, object]) -> SettingsUserActionResult:
    user_service, usuario_model = _resolve_settings_user_action_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    if admin_user is None:
        raise ValueError("Administrador no encontrado.")
    created_user = user_service.create_user(
        session=session,
        admin_user=admin_user,
        username=str(payload["username"]),
        nombre_completo=str(payload["nombre_completo"]),
        rol=payload["rol"],
        password=str(payload["password"]),
    )
    return SettingsUserActionResult(username=str(created_user.username))


def toggle_settings_user(session, *, admin_user_id: int, user_id: int) -> SettingsUserActionResult:
    user_service, usuario_model = _resolve_settings_user_action_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    target_user = session.get(usuario_model, user_id)
    if admin_user is None or target_user is None:
        raise ValueError("No se pudo cargar el usuario seleccionado.")
    updated_user = user_service.toggle_active(session, admin_user, target_user)
    return SettingsUserActionResult(
        username=str(updated_user.username),
        status_text="activado" if bool(updated_user.activo) else "desactivado",
    )


def change_settings_user_role(
    session,
    *,
    admin_user_id: int,
    user_id: int,
    new_role,
) -> SettingsUserActionResult:
    user_service, usuario_model = _resolve_settings_user_action_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    target_user = session.get(usuario_model, user_id)
    if admin_user is None or target_user is None:
        raise ValueError("No se pudo cargar el usuario seleccionado.")
    updated_user = user_service.change_role(session, admin_user, target_user, new_role)
    return SettingsUserActionResult(
        username=str(updated_user.username),
        role_label=str(new_role.value),
    )


def change_settings_user_password(
    session,
    *,
    admin_user_id: int,
    user_id: int,
    new_password: str,
) -> SettingsUserActionResult:
    user_service, usuario_model = _resolve_settings_user_action_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    target_user = session.get(usuario_model, user_id)
    if admin_user is None or target_user is None:
        raise ValueError("No se pudo cargar el usuario seleccionado.")
    updated_user = user_service.change_password(session, admin_user, target_user, new_password)
    return SettingsUserActionResult(username=str(updated_user.username))


def update_settings_user(
    session,
    *,
    admin_user_id: int,
    user_id: int,
    payload: dict[str, object],
) -> SettingsUserActionResult:
    user_service, usuario_model = _resolve_settings_user_action_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    target_user = session.get(usuario_model, user_id)
    if admin_user is None or target_user is None:
        raise ValueError("No se pudo cargar el usuario seleccionado.")
    updated_user = user_service.update_user(
        session=session,
        admin_user=admin_user,
        target_user=target_user,
        username=str(payload["username"]),
        nombre_completo=str(payload["nombre_completo"]),
        rol=payload["rol"],
    )
    return SettingsUserActionResult(username=str(updated_user.username))


def _resolve_settings_user_model():
    from pos_uniformes.database.models import Usuario

    return Usuario


def _resolve_settings_user_action_dependencies():
    from pos_uniformes.database.models import Usuario
    from pos_uniformes.services.user_service import UserService

    return UserService, Usuario
