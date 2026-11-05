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
            "3 etiquetas grandes de 29 × 90 mm",
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
            "8 piezas en 2 hojas de 4 etiquetas",
        )

    def test_el_resumen_y_el_boton_hablan_claro(self) -> None:
        """Sin «Modo seleccionado» ni el nombre del archivo: qué sale y cuántas (2026-11-05)."""
        from pos_uniformes.ui.helpers.inventory_label_preview_helper import nombre_de_modo, texto_boton_imprimir

        def r(modo, efectivas, pedidas):
            return LabelRenderResult(mode=modo, image_path=Path("/tmp/label.png"), effective_copies=efectivas, requested_copies=pedidas)

        self.assertEqual(build_inventory_label_preview_view(r("dk1221", 1, 1)).summary_text,
                         "1 etiqueta cuadrada de 23 mm, con corte entre cada una")
        self.assertEqual(build_inventory_label_preview_view(r("dk1221", 20, 20)).summary_text,
                         "20 etiquetas cuadradas de 23 mm, con corte entre cada una")
        self.assertEqual(build_inventory_label_preview_view(r("split", 1, 3)).summary_text, "3 piezas en 1 hoja de 4 etiquetas")
        self.assertNotIn("label.png", build_inventory_label_preview_view(r("standard", 2, 2)).summary_text)
        self.assertEqual(texto_boton_imprimir(None), "Imprimir etiqueta")
        self.assertEqual(texto_boton_imprimir(r("dk1221", 1, 1)), "Imprimir 1 etiqueta")
        self.assertEqual(texto_boton_imprimir(r("standard", 20, 20)), "Imprimir 20 etiquetas")
        self.assertEqual(texto_boton_imprimir(r("split", 2, 8)), "Imprimir 2 hojas")
        self.assertEqual([nombre_de_modo(m) for m in ("dk1221", "standard", "split")], ["Cuadrada", "Grande", "Tira de 4"])
        self.assertIn("23 mm", build_inventory_label_mode_hint("dk1221"))

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
        self.assertIn("Modo: Tira de 4", message)
        self.assertIn("Piezas solicitadas: 8", message)
        self.assertIn("Copias/hojas impresas: 2", message)


if __name__ == "__main__":
    unittest.main()
