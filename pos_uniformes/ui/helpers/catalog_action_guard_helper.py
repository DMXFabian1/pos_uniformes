"""Guarda copy y validacion ligera para acciones de Catalogo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogActionGuardFeedback:
    title: str
    message: str


def build_catalog_action_guard_feedback(
    *,
    action_key: str,
    has_selection: bool,
    is_admin: bool,
) -> CatalogActionGuardFeedback | None:
    action_copy = _catalog_action_copy(action_key)
    if not has_selection:
        return CatalogActionGuardFeedback(
            title="Sin seleccion",
            message=action_copy["missing_selection_message"],
        )
    if not is_admin:
        return CatalogActionGuardFeedback(
            title="Sin permisos",
            message=action_copy["permission_message"],
        )
    return None


def _catalog_action_copy(action_key: str) -> dict[str, str]:
    action_map = {
        "update_product": {
            "missing_selection_message": "Selecciona una presentacion para editar su producto.",
            "permission_message": "Solo ADMIN puede editar productos.",
        },
        "update_variant": {
            "missing_selection_message": "Selecciona una presentacion para editarla.",
            "permission_message": "Solo ADMIN puede editar presentaciones.",
        },
        "toggle_product": {
            "missing_selection_message": "Selecciona una presentacion para cambiar el estado del producto.",
            "permission_message": "Solo ADMIN puede activar o desactivar productos.",
        },
        "toggle_variant": {
            "missing_selection_message": "Selecciona una presentacion para cambiar su estado.",
            "permission_message": "Solo ADMIN puede activar o desactivar presentaciones.",
        },
        "delete_product": {
            "missing_selection_message": "Selecciona una presentacion del producto que quieres eliminar.",
            "permission_message": "Solo ADMIN puede eliminar productos.",
        },
        "delete_variant": {
            "missing_selection_message": "Selecciona una presentacion para eliminarla.",
            "permission_message": "Solo ADMIN puede eliminar presentaciones.",
        },
    }
    if action_key not in action_map:
        raise ValueError(f"Accion de catalogo no soportada: {action_key}")
    return action_map[action_key]
