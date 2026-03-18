"""Helpers visibles para usuarios en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsUserRowView:
    user_id: int
    values: tuple[object, ...]


@dataclass(frozen=True)
class SettingsUsersView:
    status_label: str
    rows: tuple[SettingsUserRowView, ...]


def build_settings_users_view(users: list[dict[str, object]]) -> SettingsUsersView:
    return SettingsUsersView(
        status_label=f"Usuarios registrados: {len(users)}",
        rows=tuple(
            SettingsUserRowView(
                user_id=int(user["id"]),
                values=(
                    user["username"],
                    user["full_name"],
                    user["role"],
                    user["active_label"],
                    user["updated_label"],
                ),
            )
            for user in users
        ),
    )


def build_settings_users_error_view(error_message: str) -> SettingsUsersView:
    return SettingsUsersView(
        status_label=f"No se pudieron cargar usuarios: {error_message}",
        rows=(),
    )
