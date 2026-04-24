"""Resolucion de seleccion para proveedores, clientes y empleadas en Configuracion."""

from __future__ import annotations


def resolve_selected_settings_row_id(*, current_row: int, raw_id: object) -> int | None:
    if current_row < 0 or raw_id is None:
        return None
    return int(raw_id)


def resolve_selected_settings_supplier_id(*, current_row: int, raw_supplier_id: object) -> int | None:
    return resolve_selected_settings_row_id(current_row=current_row, raw_id=raw_supplier_id)


def resolve_selected_settings_client_id(*, current_row: int, raw_client_id: object) -> int | None:
    return resolve_selected_settings_row_id(current_row=current_row, raw_id=raw_client_id)


def resolve_selected_settings_employee_id(*, current_row: int, raw_employee_id: object) -> int | None:
    return resolve_selected_settings_row_id(current_row=current_row, raw_id=raw_employee_id)
