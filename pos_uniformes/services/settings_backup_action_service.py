"""Acciones operativas para respaldos desde Configuracion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import sys
from typing import Callable

from pos_uniformes.services.backup_service import (
    backup_output_dir,
    create_backup,
    restore_backup,
)


@dataclass(frozen=True)
class SettingsBackupCreateResult:
    backup_file: Path
    deleted_files: tuple[Path, ...]


def create_settings_backup(*, dump_format: str, retention_days: int = 7) -> SettingsBackupCreateResult:
    backup_file, deleted_files = create_backup(
        output_dir=backup_output_dir(),
        dump_format=dump_format,
        retention_days=retention_days,
    )
    return SettingsBackupCreateResult(
        backup_file=backup_file,
        deleted_files=tuple(deleted_files),
    )


def open_settings_backup_folder(
    *,
    open_path: Callable[[Path], None] | None = None,
) -> Path:
    target_dir = backup_output_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    if open_path is None:
        _open_path_in_file_manager(target_dir)
    else:
        open_path(target_dir)
    return target_dir


def restore_settings_backup(
    backup_path: Path,
    *,
    dispose_database: Callable[[], None] | None = None,
) -> Path:
    if dispose_database is not None:
        dispose_database()
    restore_backup(backup_path)
    return backup_path


def _open_path_in_file_manager(target_dir: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(target_dir)], check=True)
        return
    if os.name == "nt":
        os.startfile(str(target_dir))
        return
    subprocess.run(["xdg-open", str(target_dir)], check=True)
