"""Mensajes y guardas operativas para proveedores, clientes y marketing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsCrmFeedbackView:
    title: str
    message: str


def build_settings_supplier_guard_feedback(
    action_key: str,
    *,
    is_admin: bool,
    has_selection: bool,
) -> SettingsCrmFeedbackView | None:
    if action_key == "create_supplier":
        if is_admin:
            return None
        return SettingsCrmFeedbackView("Sin permisos", "Solo ADMIN puede crear proveedores.")
    if has_selection:
        return None
    return SettingsCrmFeedbackView("Sin seleccion", "Selecciona un proveedor en la tabla.")


def build_settings_supplier_result_feedback(
    action_key: str,
    *,
    supplier_name: str,
    status_text: str | None = None,
) -> SettingsCrmFeedbackView:
    if action_key == "create_supplier":
        return SettingsCrmFeedbackView(
            "Proveedor creado",
            f"Proveedor '{supplier_name}' creado correctamente.",
        )
    if action_key == "update_supplier":
        return SettingsCrmFeedbackView(
            "Proveedor actualizado",
            f"Proveedor '{supplier_name}' actualizado.",
        )
    if action_key == "toggle_supplier":
        return SettingsCrmFeedbackView(
            "Proveedor actualizado",
            f"Proveedor '{supplier_name}' {status_text} correctamente.",
        )
    raise ValueError(f"Accion no soportada: {action_key}")


def build_settings_client_guard_feedback(
    action_key: str,
    *,
    is_admin: bool,
    has_selection: bool,
) -> SettingsCrmFeedbackView | None:
    if action_key == "create_client":
        if is_admin:
            return None
        return SettingsCrmFeedbackView("Sin permisos", "Solo ADMIN puede crear clientes.")
    if has_selection:
        return None
    return SettingsCrmFeedbackView("Sin seleccion", "Selecciona un cliente en la tabla.")


def build_settings_client_result_feedback(
    action_key: str,
    *,
    client_name: str,
    client_code: str | None = None,
    status_text: str | None = None,
    asset_path: str | None = None,
    asset_error: str | None = None,
) -> SettingsCrmFeedbackView:
    if action_key == "create_client":
        message = f"Cliente '{client_name}' creado correctamente."
        if asset_path is not None:
            message = f"{message}\nCredencial lista en:\n{asset_path}"
        elif asset_error:
            message = f"{message}\nLa credencial quedo pendiente: {asset_error}"
        return SettingsCrmFeedbackView("Cliente creado", message)
    if action_key == "update_client":
        message = f"Cliente '{client_name}' actualizado."
        if asset_path is not None:
            message = f"{message}\nCredencial regenerada en:\n{asset_path}"
        elif asset_error:
            message = f"{message}\nLa credencial sigue pendiente: {asset_error}"
        return SettingsCrmFeedbackView("Cliente actualizado", message)
    if action_key == "toggle_client":
        return SettingsCrmFeedbackView(
            "Cliente actualizado",
            f"Cliente '{client_name}' {status_text} correctamente.",
        )
    if action_key == "generate_client_qr":
        return SettingsCrmFeedbackView(
            "QR generado",
            f"QR del cliente '{client_code}' guardado en:\n{asset_path}",
        )
    raise ValueError(f"Accion no soportada: {action_key}")


def build_settings_marketing_guard_feedback(action_key: str, *, is_admin: bool) -> SettingsCrmFeedbackView | None:
    if is_admin:
        return None
    if action_key == "recalculate_levels":
        return SettingsCrmFeedbackView("Sin permisos", "Solo ADMIN puede recalcular niveles.")
    if action_key == "open_history":
        return SettingsCrmFeedbackView("Sin permisos", "Solo ADMIN puede consultar este historial.")
    raise ValueError(f"Accion no soportada: {action_key}")


def build_settings_marketing_result_feedback(*, total: int, changed: int) -> SettingsCrmFeedbackView:
    message = f"Niveles revisados: {total}\nClientes con cambio aplicado: {changed}"
    return SettingsCrmFeedbackView("Recalculo completado", message)
