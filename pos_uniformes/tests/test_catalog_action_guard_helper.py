from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_action_guard_helper import (
    CatalogActionGuardFeedback,
    build_catalog_action_guard_feedback,
)


class CatalogActionGuardHelperTests(unittest.TestCase):
    def test_returns_missing_selection_feedback_for_update_product(self) -> None:
        feedback = build_catalog_action_guard_feedback(
            action_key="update_product",
            has_selection=False,
            is_admin=True,
        )

        self.assertEqual(
            feedback,
            CatalogActionGuardFeedback(
                title="Sin seleccion",
                message="Selecciona una presentacion para editar su producto.",
            ),
        )

    def test_returns_permission_feedback_for_toggle_variant(self) -> None:
        feedback = build_catalog_action_guard_feedback(
            action_key="toggle_variant",
            has_selection=True,
            is_admin=False,
        )

        self.assertEqual(
            feedback,
            CatalogActionGuardFeedback(
                title="Sin permisos",
                message="Solo ADMIN puede activar o desactivar presentaciones.",
            ),
        )

    def test_returns_none_when_action_is_allowed(self) -> None:
        feedback = build_catalog_action_guard_feedback(
            action_key="delete_product",
            has_selection=True,
            is_admin=True,
        )

        self.assertIsNone(feedback)

    def test_raises_for_unknown_action_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "Accion de catalogo no soportada"):
            build_catalog_action_guard_feedback(
                action_key="desconocida",
                has_selection=True,
                is_admin=True,
            )


if __name__ == "__main__":
    unittest.main()
