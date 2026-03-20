"""Helpers visibles para el modulo de respaldos en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos_uniformes.utils.date_format import format_display_datetime


@dataclass(frozen=True)
class SettingsBackupRowView:
    path_value: str
    values: tuple[object, ...]


@dataclass(frozen=True)
class SettingsBackupView:
    location_label: str
    status_label: str
    automatic_status_label: str
    automatic_detail_label: str
    rows: tuple[SettingsBackupRowView, ...]


def _humanize_hours(hours: float) -> str:
    if hours < 1:
        return "menos de 1 hora"
    if hours < 24:
        rounded = int(hours)
        return f"{rounded} hora{'s' if rounded != 1 else ''}"
    days = int(hours // 24)
    return f"{days} dia{'s' if days != 1 else ''}"


def build_settings_backup_automatic_status_view(
    *,
    automatic_status: dict[str, object] | None,
    now: datetime | None = None,
    stale_after_hours: int = 36,
) -> tuple[str, str]:
    if automatic_status is None:
        return (
            "Automatico: sin informacion todavia.",
            "Programa scripts/run_scheduled_backup.py desde el sistema para empezar a monitorear respaldos automaticos.",
        )

    reference_now = now or datetime.now()
    last_run_at = automatic_status.get("last_run_at")
    last_success_at = automatic_status.get("last_success_at")
    backup_name = automatic_status.get("backup_name")
    retention_days = automatic_status.get("retention_days")
    last_error = automatic_status.get("last_error")

    run_label = format_display_datetime(last_run_at if isinstance(last_run_at, datetime) else None, empty="sin ejecucion")
    success_dt = last_success_at if isinstance(last_success_at, datetime) else None
    success_label = format_display_datetime(success_dt, empty="sin respaldo correcto")
    retention_label = (
        f"Retencion: {retention_days} dias" if isinstance(retention_days, int) and retention_days > 0 else "Retencion: sin dato"
    )

    if success_dt is None:
        summary = "Automatico: pendiente de primer respaldo correcto."
        detail = f"Ultimo intento: {run_label} | {retention_label}"
        if isinstance(last_error, str) and last_error:
            detail = f"{detail} | Error: {last_error}"
        return summary, detail

    age_hours = max((reference_now - success_dt).total_seconds() / 3600, 0)
    age_label = _humanize_hours(age_hours)
    file_label = f"Archivo: {backup_name}" if isinstance(backup_name, str) and backup_name else "Archivo: sin dato"

    if isinstance(last_error, str) and last_error:
        return (
            f"Automatico: fallo en la ultima ejecucion | Ultimo correcto: {success_label}",
            f"Ultimo intento: {run_label} | {file_label} | {retention_label} | Error: {last_error}",
        )

    if age_hours > stale_after_hours:
        return (
            f"Automatico: revisar | Ultimo respaldo correcto hace {age_label}",
            f"Ultimo correcto: {success_label} | {file_label} | {retention_label}",
        )

    return (
        f"Automatico: OK | Ultimo respaldo correcto hace {age_label}",
        f"Ultimo correcto: {success_label} | {file_label} | {retention_label}",
    )


def build_settings_backup_view(
    *,
    backup_dir: str,
    backups: list[dict[str, object]],
    automatic_status: dict[str, object] | None = None,
    now: datetime | None = None,
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
    automatic_status_label, automatic_detail_label = build_settings_backup_automatic_status_view(
        automatic_status=automatic_status,
        now=now,
    )
    return SettingsBackupView(
        location_label=f"Carpeta de respaldos: {backup_dir}",
        status_label=status_label,
        automatic_status_label=automatic_status_label,
        automatic_detail_label=automatic_detail_label,
        rows=rows,
    )

def build_settings_backup_error_view(
    *,
    backup_dir: str,
    error_message: str,
    automatic_status: dict[str, object] | None = None,
    now: datetime | None = None,
) -> SettingsBackupView:
    automatic_status_label, automatic_detail_label = build_settings_backup_automatic_status_view(
        automatic_status=automatic_status,
        now=now,
    )
    return SettingsBackupView(
        location_label=f"Carpeta de respaldos: {backup_dir}",
        status_label=f"No se pudo leer la carpeta de respaldos: {error_message}",
        automatic_status_label=automatic_status_label,
        automatic_detail_label=automatic_detail_label,
        rows=(),
    )
