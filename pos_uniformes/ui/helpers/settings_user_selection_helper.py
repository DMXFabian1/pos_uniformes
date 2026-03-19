"""Resolucion de seleccion para usuarios en Configuracion."""

from __future__ import annotations


def resolve_selected_settings_user_id(*, current_row: int, raw_user_id: object) -> int | None:
    if current_row < 0 or raw_user_id is None:
        return None
    return int(raw_user_id)
