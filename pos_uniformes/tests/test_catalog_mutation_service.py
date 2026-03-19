from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pos_uniformes.services.catalog_mutation_service import (
    delete_catalog_product,
    delete_catalog_variant,
    toggle_catalog_product_state,
    toggle_catalog_variant_state,
)


class CatalogMutationServiceTests(unittest.TestCase):
    def test_toggle_catalog_product_state_delegates_to_catalog_service(self) -> None:
        usuario = object()
        producto = object()

        def fake_get(model, entity_id):
            if entity_id == 4:
                return usuario
            if entity_id == 8:
                return producto
            return None

        session = SimpleNamespace(get=fake_get)

        catalog_service = SimpleNamespace(cambiar_estado_producto=Mock())

        with patch(
            "pos_uniformes.services.catalog_mutation_service._resolve_catalog_mutation_dependencies",
            return_value=(object, object, object, catalog_service),
        ):
            toggle_catalog_product_state(
                session,
                user_id=4,
                product_id=8,
                target_state=False,
            )

        catalog_service.cambiar_estado_producto.assert_called_once_with(session, usuario, producto, False)

    def test_toggle_catalog_variant_state_raises_for_missing_variant(self) -> None:
        usuario = object()
        session = SimpleNamespace(get=lambda _model, entity_id: usuario if entity_id == 4 else None)

        with patch(
            "pos_uniformes.services.catalog_mutation_service._resolve_catalog_mutation_dependencies",
            return_value=(object, object, object, SimpleNamespace(cambiar_estado_variante=Mock())),
        ):
            with self.assertRaisesRegex(ValueError, "No se pudo cargar la presentacion"):
                toggle_catalog_variant_state(
                    session,
                    user_id=4,
                    variant_id=12,
                    target_state=True,
                )

    def test_delete_catalog_product_delegates_to_catalog_service(self) -> None:
        usuario = object()
        producto = object()

        def fake_get(model, entity_id):
            if entity_id == 4:
                return usuario
            if entity_id == 8:
                return producto
            return None

        session = SimpleNamespace(get=fake_get)

        catalog_service = SimpleNamespace(eliminar_producto=Mock())

        with patch(
            "pos_uniformes.services.catalog_mutation_service._resolve_catalog_mutation_dependencies",
            return_value=(object, object, object, catalog_service),
        ):
            delete_catalog_product(
                session,
                user_id=4,
                product_id=8,
            )

        catalog_service.eliminar_producto.assert_called_once_with(session, usuario, producto)

    def test_delete_catalog_variant_delegates_to_catalog_service(self) -> None:
        usuario = object()
        variante = object()

        def fake_get(model, entity_id):
            if entity_id == 4:
                return usuario
            if entity_id == 10:
                return variante
            return None

        session = SimpleNamespace(get=fake_get)

        catalog_service = SimpleNamespace(eliminar_variante=Mock())

        with patch(
            "pos_uniformes.services.catalog_mutation_service._resolve_catalog_mutation_dependencies",
            return_value=(object, object, object, catalog_service),
        ):
            delete_catalog_variant(
                session,
                user_id=4,
                variant_id=10,
            )

        catalog_service.eliminar_variante.assert_called_once_with(session, usuario, variante)


if __name__ == "__main__":
    unittest.main()
