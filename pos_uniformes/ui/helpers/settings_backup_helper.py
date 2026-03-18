"""Helpers visibles para el modulo de respaldos en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsBackupRowView:
    path_value: str
    values: tuple[object, ...]


@dataclass(frozen=True)
class SettingsBackupView:
    location_label: str
    status_label: str
    rows: tuple[SettingsBackupRowView, ...]


def build_settings_backup_view(
    *,
    backup_dir: str,
    backups: list[dict[str, object]],
) -> SettingsBackupView:
    rows = tuple(
        SettingsBackupRowView(
            path_value=str(backup["path_value"]),
            values=(
                backup["name"],
                backup["format_label"],
                backup["modified_label"],
                backup["size_label"],
                backup["restorable_label"],
            ),
        )
        for backup in backups
    )
    if backups:
        status_label = f"Respaldos disponibles: {len(backups)} | Ultimo: {backups[0]['name']}"
    else:
        status_label = "No hay respaldos todavia en la carpeta configurada."
    return SettingsBackupView(
        location_label=f"Carpeta de respaldos: {backup_dir}",
        status_label=status_label,
        rows=rows,
    )


def build_settings_backup_error_view(*, backup_dir: str, error_message: str) -> SettingsBackupView:
    return SettingsBackupView(
        location_label=f"Carpeta de respaldos: {backup_dir}",
        status_label=f"No se pudo leer la carpeta de respaldos: {error_message}",
        rows=(),
    )
