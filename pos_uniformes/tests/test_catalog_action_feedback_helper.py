from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_action_feedback_helper import (
    CatalogConfirmationView,
    CatalogResultView,
    build_catalog_delete_confirmation,
    build_catalog_error_title,
    build_catalog_success_result,
)


class CatalogActionFeedbackHelperTests(unittest.TestCase):
    def test_build_catalog_delete_confirmation_for_product(self) -> None:
        view = build_catalog_delete_confirmation(
            action_key="delete_product",
            item_label="Playera deportiva",
        )

        self.assertEqual(
            view,
            CatalogConfirmationView(
                title="Eliminar producto",
                message=(
                    "Se intentara eliminar el producto 'Playera deportiva'.\n\n"
                    "Solo se eliminara si ninguna presentacion tiene stock ni historial.\n"
                    "Si existe historial, usa desactivar en lugar de eliminar.\n\n"
                    "Deseas continuar?"
                ),
            ),
        )

    def test_build_catalog_success_result_for_toggle_variant_activate(self) -> None:
        view = build_catalog_success_result(
            action_key="toggle_variant_activate",
            item_label="SKU-010",
        )

        self.assertEqual(
            view,
            CatalogResultView(
                title="Presentacion actualizada",
                message="Presentacion lista para activar correctamente.",
            ),
        )

    def test_build_catalog_error_title_for_delete_variant(self) -> None:
        self.assertEqual(build_catalog_error_title("delete_variant"), "No se pudo eliminar")

    def test_build_catalog_success_result_raises_for_unknown_action(self) -> None:
        with self.assertRaisesRegex(ValueError, "Accion de resultado no soportada"):
            build_catalog_success_result(
                action_key="otra",
                item_label="X",
            )


if __name__ == "__main__":
    unittest.main()
