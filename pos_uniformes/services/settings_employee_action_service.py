"""Mutaciones y snapshots operativos para empleadas en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsEmployeePromptSnapshot:
    code: str
    full_name: str


@dataclass(frozen=True)
class SettingsEmployeeActionResult:
    employee_name: str
    employee_code: str
    status_text: str | None = None


def load_settings_employee_prompt_snapshot(session, *, employee_id: int) -> SettingsEmployeePromptSnapshot:
    employee_model = _resolve_settings_employee_model()
    employee = session.get(employee_model, employee_id)
    if employee is None:
        raise ValueError("No se encontro la empleada seleccionada.")
    return SettingsEmployeePromptSnapshot(
        code=str(employee.codigo),
        full_name=str(employee.nombre_completo),
    )


def create_settings_employee(session, *, admin_user_id: int, payload: dict[str, object]) -> SettingsEmployeeActionResult:
    employee_service, usuario_model = _resolve_settings_employee_action_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    if admin_user is None:
        raise ValueError("Administrador no encontrado.")
    employee = employee_service.create_employee(
        session=session,
        admin_user=admin_user,
        codigo=str(payload["codigo"]),
        nombre_completo=str(payload["nombre_completo"]),
    )
    return SettingsEmployeeActionResult(
        employee_name=str(employee.nombre_completo),
        employee_code=str(employee.codigo),
    )


def update_settings_employee(
    session,
    *,
    admin_user_id: int,
    employee_id: int,
    payload: dict[str, object],
) -> SettingsEmployeeActionResult:
    employee_service, usuario_model, employee_model = _resolve_settings_employee_update_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    employee = session.get(employee_model, employee_id)
    if admin_user is None or employee is None:
        raise ValueError("No se pudo cargar la empleada seleccionada.")
    updated_employee = employee_service.update_employee(
        session=session,
        admin_user=admin_user,
        employee=employee,
        codigo=str(payload["codigo"]),
        nombre_completo=str(payload["nombre_completo"]),
    )
    return SettingsEmployeeActionResult(
        employee_name=str(updated_employee.nombre_completo),
        employee_code=str(updated_employee.codigo),
    )


def toggle_settings_employee(session, *, admin_user_id: int, employee_id: int) -> SettingsEmployeeActionResult:
    employee_service, usuario_model, employee_model = _resolve_settings_employee_update_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    employee = session.get(employee_model, employee_id)
    if admin_user is None or employee is None:
        raise ValueError("No se pudo cargar la empleada seleccionada.")
    updated_employee = employee_service.toggle_active(session, admin_user, employee)
    return SettingsEmployeeActionResult(
        employee_name=str(updated_employee.nombre_completo),
        employee_code=str(updated_employee.codigo),
        status_text="activada" if bool(updated_employee.activo) else "desactivada",
    )


def _resolve_settings_employee_model():
    from pos_uniformes.database.models import Empleada

    return Empleada


def _resolve_settings_employee_action_dependencies():
    from pos_uniformes.database.models import Usuario
    from pos_uniformes.services.employee_identity_service import EmployeeIdentityService

    return EmployeeIdentityService, Usuario


def _resolve_settings_employee_update_dependencies():
    from pos_uniformes.database.models import Empleada, Usuario
    from pos_uniformes.services.employee_identity_service import EmployeeIdentityService

    return EmployeeIdentityService, Usuario, Empleada
