"""Helpers visibles para proveedores en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsSupplierRowView:
    supplier_id: int
    values: tuple[object, ...]
    status_tone: str


@dataclass(frozen=True)
class SettingsSuppliersView:
    status_label: str
    rows: tuple[SettingsSupplierRowView, ...]


def build_settings_suppliers_view(suppliers: list[dict[str, object]]) -> SettingsSuppliersView:
    return SettingsSuppliersView(
        status_label=f"Proveedores registrados: {len(suppliers)}",
        rows=tuple(
            SettingsSupplierRowView(
                supplier_id=int(supplier["id"]),
                values=(
                    supplier["name"],
                    supplier["phone"],
                    supplier["email"],
                    supplier["address"],
                    supplier["active_label"],
                    supplier["updated_label"],
                ),
                status_tone="positive" if bool(supplier["active"]) else "muted",
            )
            for supplier in suppliers
        ),
    )


def build_settings_suppliers_error_view(error_message: str) -> SettingsSuppliersView:
    return SettingsSuppliersView(
        status_label=f"No se pudieron cargar proveedores: {error_message}",
        rows=(),
    )
