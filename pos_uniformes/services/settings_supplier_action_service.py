"""Mutaciones y snapshots operativos para proveedores en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsSupplierPromptSnapshot:
    name: str
    phone: str
    email: str
    address: str


@dataclass(frozen=True)
class SettingsSupplierActionResult:
    supplier_name: str
    status_text: str | None = None


def load_settings_supplier_prompt_snapshot(session, *, supplier_id: int) -> SettingsSupplierPromptSnapshot:
    proveedor_model = _resolve_settings_supplier_model()
    supplier = session.get(proveedor_model, supplier_id)
    if supplier is None:
        raise ValueError("No se encontro el proveedor seleccionado.")
    return SettingsSupplierPromptSnapshot(
        name=str(supplier.nombre),
        phone=str(supplier.telefono or ""),
        email=str(supplier.email or ""),
        address=str(supplier.direccion or ""),
    )


def create_settings_supplier(session, *, admin_user_id: int, payload: dict[str, object]) -> SettingsSupplierActionResult:
    supplier_service, usuario_model = _resolve_settings_supplier_action_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    if admin_user is None:
        raise ValueError("Administrador no encontrado.")
    supplier = supplier_service.create_supplier(
        session=session,
        admin_user=admin_user,
        nombre=str(payload["nombre"]),
        telefono=str(payload["telefono"]),
        email=str(payload["email"]),
        direccion=str(payload["direccion"]),
    )
    return SettingsSupplierActionResult(supplier_name=str(supplier.nombre))


def update_settings_supplier(
    session,
    *,
    admin_user_id: int,
    supplier_id: int,
    payload: dict[str, object],
) -> SettingsSupplierActionResult:
    supplier_service, usuario_model, proveedor_model = _resolve_settings_supplier_update_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    supplier = session.get(proveedor_model, supplier_id)
    if admin_user is None or supplier is None:
        raise ValueError("No se pudo cargar el proveedor seleccionado.")
    updated_supplier = supplier_service.update_supplier(
        session=session,
        admin_user=admin_user,
        supplier=supplier,
        nombre=str(payload["nombre"]),
        telefono=str(payload["telefono"]),
        email=str(payload["email"]),
        direccion=str(payload["direccion"]),
    )
    return SettingsSupplierActionResult(supplier_name=str(updated_supplier.nombre))


def toggle_settings_supplier(session, *, admin_user_id: int, supplier_id: int) -> SettingsSupplierActionResult:
    supplier_service, usuario_model, proveedor_model = _resolve_settings_supplier_update_dependencies()
    admin_user = session.get(usuario_model, admin_user_id)
    supplier = session.get(proveedor_model, supplier_id)
    if admin_user is None or supplier is None:
        raise ValueError("No se pudo cargar el proveedor seleccionado.")
    updated_supplier = supplier_service.toggle_active(session, admin_user, supplier)
    return SettingsSupplierActionResult(
        supplier_name=str(updated_supplier.nombre),
        status_text="activado" if bool(updated_supplier.activo) else "desactivado",
    )


def _resolve_settings_supplier_model():
    from pos_uniformes.database.models import Proveedor

    return Proveedor


def _resolve_settings_supplier_action_dependencies():
    from pos_uniformes.database.models import Usuario
    from pos_uniformes.services.supplier_service import SupplierService

    return SupplierService, Usuario


def _resolve_settings_supplier_update_dependencies():
    from pos_uniformes.database.models import Proveedor, Usuario
    from pos_uniformes.services.supplier_service import SupplierService

    return SupplierService, Usuario, Proveedor
