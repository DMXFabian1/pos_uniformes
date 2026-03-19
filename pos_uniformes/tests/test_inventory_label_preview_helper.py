from __future__ import annotations

from pathlib import Path
import unittest

from pos_uniformes.ui.helpers.inventory_label_preview_helper import (
    build_error_inventory_label_preview_view,
    build_inventory_label_mode_hint,
    build_inventory_label_preview_view,
    build_inventory_label_print_confirmation,
)
from pos_uniformes.utils.label_generator import LabelRenderResult


class InventoryLabelPreviewHelperTests(unittest.TestCase):
    def test_build_error_inventory_label_preview_view_disables_print(self) -> None:
        view = build_error_inventory_label_preview_view("Fallo el render")

        self.assertEqual(view.preview_text, "No se pudo generar la etiqueta")
        self.assertEqual(view.summary_text, "No se pudo preparar la vista previa.\nDetalle: Fallo el render")
        self.assertFalse(view.print_enabled)

    def test_build_inventory_label_mode_hint_for_standard(self) -> None:
        self.assertIn("etiqueta por pieza", build_inventory_label_mode_hint("standard"))

    def test_build_inventory_label_mode_hint_for_split(self) -> None:
        self.assertIn("4 etiquetas por hoja", build_inventory_label_mode_hint("split"))

    def test_build_inventory_label_preview_view_for_standard_mode(self) -> None:
        result = LabelRenderResult(
            mode="standard",
            image_path=Path("/tmp/label.png"),
            effective_copies=3,
            requested_copies=3,
        )

        view = build_inventory_label_preview_view(result)

        self.assertEqual(view.preview_text, "Sin vista previa")
        self.assertEqual(
            view.summary_text,
            "Modo seleccionado: Normal\nCopias a imprimir: 3\nArchivo generado: label.png",
        )
        self.assertTrue(view.print_enabled)

    def test_build_inventory_label_preview_view_for_split_mode(self) -> None:
        result = LabelRenderResult(
            mode="split",
            image_path=Path("/tmp/label.png"),
            effective_copies=2,
            requested_copies=8,
        )

        view = build_inventory_label_preview_view(result)

        self.assertEqual(
            view.summary_text,
            "Modo seleccionado: Split\nPiezas solicitadas: 8\nHojas a imprimir: 2\nArchivo generado: label.png",
        )

    def test_build_inventory_label_print_confirmation(self) -> None:
        result = LabelRenderResult(
            mode="split",
            image_path=Path("/tmp/label.png"),
            effective_copies=2,
            requested_copies=8,
        )

        message = build_inventory_label_print_confirmation(
            sku="SKU-008",
            result=result,
        )

        self.assertIn("SKU-008", message)
        self.assertIn("Modo: Split", message)
        self.assertIn("Piezas solicitadas: 8", message)
        self.assertIn("Copias/hojas impresas: 2", message)


if __name__ == "__main__":
    unittest.main()
