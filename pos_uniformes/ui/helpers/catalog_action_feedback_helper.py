"""Copy visible para confirmaciones y resultados de acciones de Catalogo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogConfirmationView:
    title: str
    message: str


@dataclass(frozen=True)
class CatalogResultView:
    title: str
    message: str


def build_catalog_delete_confirmation(
    *,
    action_key: str,
    item_label: str,
) -> CatalogConfirmationView:
    if action_key == "delete_product":
        return CatalogConfirmationView(
            title="Eliminar producto",
            message=(
                f"Se intentara eliminar el producto '{item_label}'.\n\n"
                "Solo se eliminara si ninguna presentacion tiene stock ni historial.\n"
                "Si existe historial, usa desactivar en lugar de eliminar.\n\n"
                "Deseas continuar?"
            ),
        )
    if action_key == "delete_variant":
        return CatalogConfirmationView(
            title="Eliminar presentacion",
            message=(
                f"Se intentara eliminar la presentacion '{item_label}'.\n\n"
                "Solo se eliminara si no tiene stock ni historial.\n"
                "Si existe historial, usa desactivar en lugar de eliminar.\n\n"
                "Deseas continuar?"
            ),
        )
    raise ValueError(f"Accion de confirmacion no soportada: {action_key}")


def build_catalog_success_result(
    *,
    action_key: str,
    item_label: str,
) -> CatalogResultView:
    result_map = {
        "update_product": CatalogResultView(
            title="Producto actualizado",
            message=f"Producto '{item_label}' actualizado correctamente.",
        ),
        "update_variant": CatalogResultView(
            title="Presentacion actualizada",
            message=f"Presentacion '{item_label}' actualizada correctamente.",
        ),
        "toggle_product_activate": CatalogResultView(
            title="Producto actualizado",
            message="Producto listo para activar correctamente.",
        ),
        "toggle_product_deactivate": CatalogResultView(
            title="Producto actualizado",
            message="Producto listo para desactivar correctamente.",
        ),
        "toggle_variant_activate": CatalogResultView(
            title="Presentacion actualizada",
            message="Presentacion lista para activar correctamente.",
        ),
        "toggle_variant_deactivate": CatalogResultView(
            title="Presentacion actualizada",
            message="Presentacion lista para desactivar correctamente.",
        ),
        "delete_product": CatalogResultView(
            title="Producto eliminado",
            message=f"Producto '{item_label}' eliminado correctamente.",
        ),
        "delete_variant": CatalogResultView(
            title="Presentacion eliminada",
            message=f"Presentacion '{item_label}' eliminada correctamente.",
        ),
    }
    if action_key not in result_map:
        raise ValueError(f"Accion de resultado no soportada: {action_key}")
    return result_map[action_key]


def build_catalog_error_title(action_key: str) -> str:
    error_map = {
        "toggle_product": "Estado no actualizado",
        "toggle_variant": "Estado no actualizado",
        "delete_product": "No se pudo eliminar",
        "delete_variant": "No se pudo eliminar",
    }
    if action_key not in error_map:
        raise ValueError(f"Accion de error no soportada: {action_key}")
    return error_map[action_key]
