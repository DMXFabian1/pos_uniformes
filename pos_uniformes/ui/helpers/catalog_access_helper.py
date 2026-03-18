"""Helpers visibles para permisos y acciones del tab Catalogo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogAccessView:
    permission_label: str
    create_product_enabled: bool
    create_variant_enabled: bool
    update_product_enabled: bool
    update_variant_enabled: bool
    toggle_product_enabled: bool
    toggle_variant_enabled: bool
    delete_product_enabled: bool
    delete_variant_enabled: bool
    quick_setup_visible: bool


def build_catalog_access_view(*, is_admin: bool) -> CatalogAccessView:
    return CatalogAccessView(
        permission_label=(
            "Esta pestaña es de consulta. Las altas, cambios de precio y existencias se gestionan en Inventario."
            if is_admin
            else "Consulta precio, stock y estado de cada presentacion sin salir de caja."
        ),
        create_product_enabled=is_admin,
        create_variant_enabled=is_admin,
        update_product_enabled=is_admin,
        update_variant_enabled=is_admin,
        toggle_product_enabled=is_admin,
        toggle_variant_enabled=is_admin,
        delete_product_enabled=is_admin,
        delete_variant_enabled=is_admin,
        quick_setup_visible=is_admin,
    )
