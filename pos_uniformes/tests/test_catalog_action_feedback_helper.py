from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_action_feedback_helper import (
    CatalogConfirmationView,
    CatalogResultView,
    build_catalog_delete_confirmation,
    build_catalog_error_title,
    build_catalog_success_result,
    build_product_delete_label,
    build_variant_delete_label,
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


    def test_build_variant_delete_label_includes_product_talla_color_stock_precio(self) -> None:
        row = {
            "sku": "SKU-007",
            "producto_nombre": "Pants Deportivo",
            "talla": "14",
            "color": "Azul",
            "stock_actual": 5,
            "precio_venta": "150.00",
        }
        label = build_variant_delete_label(row)
        self.assertIn("SKU-007", label)
        self.assertIn("Pants Deportivo", label)
        self.assertIn("14", label)
        self.assertIn("Azul", label)
        self.assertIn("Stock: 5", label)
        self.assertIn("150.00", label)

    def test_build_variant_delete_label_handles_missing_optional_fields(self) -> None:
        row = {"sku": "SKU-001"}
        label = build_variant_delete_label(row)
        self.assertIn("SKU-001", label)

    def test_build_product_delete_label_includes_brand(self) -> None:
        row = {"producto_nombre": "Playera Oficial", "marca_nombre": "Marca Norte"}
        label = build_product_delete_label(row)
        self.assertIn("Playera Oficial", label)
        self.assertIn("Marca Norte", label)

    def test_build_product_delete_label_without_brand(self) -> None:
        row = {"producto_nombre": "Playera Oficial", "marca_nombre": ""}
        label = build_product_delete_label(row)
        self.assertEqual(label, "Playera Oficial")


if __name__ == "__main__":
    unittest.main()
