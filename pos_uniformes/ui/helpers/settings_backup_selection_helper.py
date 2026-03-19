"""Resolucion de seleccion para respaldos en Configuracion."""

from __future__ import annotations

from pathlib import Path


def resolve_selected_settings_backup_path(*, current_row: int, raw_path: object) -> Path | None:
    if current_row < 0:
        return None
    if raw_path in {None, ""}:
        return None
    return Path(str(raw_path))
