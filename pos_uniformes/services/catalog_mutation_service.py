"""Mutaciones operativas de Catalogo fuera de MainWindow."""

from __future__ import annotations

def toggle_catalog_product_state(
    session,
    *,
    user_id: int,
    product_id: int,
    target_state: bool,
) -> None:
    Usuario, Producto, _, CatalogService = _resolve_catalog_mutation_dependencies()
    usuario = session.get(Usuario, user_id)
    producto = session.get(Producto, int(product_id))
    if usuario is None or producto is None:
        raise ValueError("No se pudo cargar el producto.")
    CatalogService.cambiar_estado_producto(session, usuario, producto, target_state)


def toggle_catalog_variant_state(
    session,
    *,
    user_id: int,
    variant_id: int,
    target_state: bool,
) -> None:
    Usuario, _, Variante, CatalogService = _resolve_catalog_mutation_dependencies()
    usuario = session.get(Usuario, user_id)
    variante = session.get(Variante, int(variant_id))
    if usuario is None or variante is None:
        raise ValueError("No se pudo cargar la presentacion.")
    CatalogService.cambiar_estado_variante(session, usuario, variante, target_state)


def delete_catalog_product(
    session,
    *,
    user_id: int,
    product_id: int,
) -> None:
    Usuario, Producto, _, CatalogService = _resolve_catalog_mutation_dependencies()
    usuario = session.get(Usuario, user_id)
    producto = session.get(Producto, int(product_id))
    if usuario is None or producto is None:
        raise ValueError("No se pudo cargar el producto.")
    CatalogService.eliminar_producto(session, usuario, producto)


def delete_catalog_variant(
    session,
    *,
    user_id: int,
    variant_id: int,
) -> None:
    Usuario, _, Variante, CatalogService = _resolve_catalog_mutation_dependencies()
    usuario = session.get(Usuario, user_id)
    variante = session.get(Variante, int(variant_id))
    if usuario is None or variante is None:
        raise ValueError("No se pudo cargar la presentacion.")
    CatalogService.eliminar_variante(session, usuario, variante)


def _resolve_catalog_mutation_dependencies():
    try:
        from pos_uniformes.database.models import Producto, Usuario, Variante
        from pos_uniformes.services.catalog_service import CatalogService
    except ModuleNotFoundError:
        Producto = object
        Usuario = object
        Variante = object

        class _MissingCatalogService:
            @staticmethod
            def cambiar_estado_producto(*_args, **_kwargs) -> None:
                return None

            @staticmethod
            def cambiar_estado_variante(*_args, **_kwargs) -> None:
                return None

            @staticmethod
            def eliminar_producto(*_args, **_kwargs) -> None:
                return None

            @staticmethod
            def eliminar_variante(*_args, **_kwargs) -> None:
                return None

        CatalogService = _MissingCatalogService
    return Usuario, Producto, Variante, CatalogService
