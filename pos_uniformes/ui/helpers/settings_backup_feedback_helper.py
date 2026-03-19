"""Mensajes y guardas operativas para respaldos en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SettingsBackupFeedbackView:
    title: str
    message: str


def build_settings_backup_guard_feedback(
    action_key: str,
    *,
    is_admin: bool,
    backup_path: Path | None = None,
) -> SettingsBackupFeedbackView | None:
    if action_key == "create_backup":
        if is_admin:
            return None
        return SettingsBackupFeedbackView(
            title="Sin permisos",
            message="Solo ADMIN puede crear respaldos manuales.",
        )
    if action_key == "restore_backup":
        if not is_admin:
            return SettingsBackupFeedbackView(
                title="Sin permisos",
                message="Solo ADMIN puede restaurar respaldos.",
            )
        if backup_path is None:
            return SettingsBackupFeedbackView(
                title="Sin seleccion",
                message="Selecciona un respaldo en la tabla.",
            )
        if backup_path.suffix != ".dump":
            return SettingsBackupFeedbackView(
                title="Formato no soportado",
                message="La restauracion desde la app solo soporta respaldos .dump. Crea uno en formato restaurable.",
            )
    return None


def build_settings_backup_restore_confirmation(backup_name: str) -> SettingsBackupFeedbackView:
    return SettingsBackupFeedbackView(
        title="Restaurar respaldo",
        message=(
            f"Se restaurara el respaldo '{backup_name}' sobre la base actual.\n\n"
            "Esta accion reemplaza la informacion actual del POS.\n"
            "Asegurate de tener un respaldo reciente antes de continuar.\n\n"
            "Deseas continuar?"
        ),
    )


def build_settings_backup_result_feedback(
    action_key: str,
    *,
    backup_name: str,
    deleted_count: int = 0,
) -> SettingsBackupFeedbackView:
    if action_key == "create_backup":
        deleted_note = f" | Rotacion elimino {deleted_count} respaldo(s)." if deleted_count else ""
        return SettingsBackupFeedbackView(
            title="Respaldo creado",
            message=f"Se genero {backup_name}{deleted_note}",
        )
    if action_key == "restore_backup":
        return SettingsBackupFeedbackView(
            title="Restauracion completada",
            message=f"Se restauro {backup_name} correctamente.",
        )
    raise ValueError(f"Accion no soportada: {action_key}")
