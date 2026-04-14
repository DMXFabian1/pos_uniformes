"""Helpers visibles para empleadas en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsEmployeeRowView:
    employee_id: int
    values: tuple[object, ...]
    activity_tone: str
    pin_tone: str
    qr_tone: str
    card_tone: str
    status_tone: str


@dataclass(frozen=True)
class SettingsEmployeesView:
    status_label: str
    rows: tuple[SettingsEmployeeRowView, ...]


def build_settings_employees_view(employees: list[dict[str, object]]) -> SettingsEmployeesView:
    return SettingsEmployeesView(
        status_label=f"Empleadas registradas: {len(employees)}",
        rows=tuple(
            SettingsEmployeeRowView(
                employee_id=int(employee["id"]),
                values=(
                    employee["code"],
                    employee["name"],
                    employee["display_name"],
                    employee["activity_label"],
                    employee["pin_label"],
                    employee["qr_label"],
                    employee["card_label"],
                    employee["active_label"],
                    employee["updated_label"],
                ),
                activity_tone=str(employee["activity_tone"]),
                pin_tone="positive" if str(employee["pin_label"]) == "Listo" else "warning",
                qr_tone="positive" if str(employee["qr_label"]) == "Listo" else "warning",
                card_tone="positive" if str(employee["card_label"]) == "Lista" else "muted",
                status_tone="positive" if bool(employee["active"]) else "muted",
            )
            for employee in employees
        ),
    )


def build_settings_employees_error_view(error_message: str) -> SettingsEmployeesView:
    return SettingsEmployeesView(
        status_label=f"No se pudieron cargar empleadas: {error_message}",
        rows=(),
    )
