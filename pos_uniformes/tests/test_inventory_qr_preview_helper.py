from __future__ import annotations

from types import SimpleNamespace
import unittest

from pos_uniformes.ui.helpers.inventory_qr_preview_helper import (
    build_available_inventory_qr_preview_view,
    build_empty_inventory_qr_preview_view,
    build_error_inventory_qr_preview_view,
    build_pending_inventory_qr_preview_view,
    build_inventory_qr_preview_selection,
)


class InventoryQrPreviewHelperTests(unittest.TestCase):
    def test_build_empty_inventory_qr_preview_view(self) -> None:
        view = build_empty_inventory_qr_preview_view()

        self.assertEqual(view.button_label, "Generar QR")
        self.assertEqual(view.info_label, "")
        self.assertEqual(view.status_text, "Sin seleccion")
        self.assertEqual(view.status_tone, "neutral")
        self.assertEqual(view.placeholder_text, "QR pendiente")
        self.assertFalse(view.preview_available)

    def test_build_pending_inventory_qr_preview_view(self) -> None:
        view = build_pending_inventory_qr_preview_view(
            sku="SKU-101",
            product_name="Chamarra Deportiva | Primaria | Chamarra #17",
            talla="14",
            color="Azul Marino",
        )

        self.assertEqual(view.button_label, "Generar QR")
        self.assertEqual(
            view.info_label,
            "SKU-101 | Chamarra Deportiva | Primaria | Chamarra | talla 14 | color Azul Marino",
        )
        self.assertEqual(view.status_text, "QR pendiente. Genera la etiqueta cuando la necesites.")
        self.assertEqual(view.status_tone, "warning")
        self.assertEqual(view.placeholder_text, "QR pendiente")
        self.assertFalse(view.preview_available)

    def test_build_available_inventory_qr_preview_view(self) -> None:
        view = build_available_inventory_qr_preview_view(
            sku="SKU-202",
            product_name="Playera Polo",
            talla="12",
            color="Blanco",
            file_name="SKU-202.png",
        )

        self.assertEqual(view.button_label, "Regenerar QR")
        self.assertEqual(
            view.info_label,
            "SKU-202 | Playera Polo | talla 12 | color Blanco",
        )
        self.assertEqual(view.status_text, "QR disponible: SKU-202.png")
        self.assertEqual(view.status_tone, "positive")
        self.assertEqual(view.placeholder_text, "")
        self.assertTrue(view.preview_available)

    def test_build_error_inventory_qr_preview_view(self) -> None:
        view = build_error_inventory_qr_preview_view()

        self.assertEqual(view.button_label, "Generar QR")
        self.assertEqual(view.info_label, "")
        self.assertEqual(view.status_text, "Sin datos de QR")
        self.assertEqual(view.status_tone, "muted")
        self.assertEqual(view.placeholder_text, "QR pendiente")
        self.assertFalse(view.preview_available)

    def test_build_inventory_qr_preview_selection_extracts_display_fields(self) -> None:
        variante = SimpleNamespace(
            sku="SKU-303",
            talla="16",
            color="Azul",
            producto=SimpleNamespace(nombre="Pants Deportivo 3 Piezas"),
        )

        selection = build_inventory_qr_preview_selection(variante)

        self.assertEqual(selection.sku, "SKU-303")
        self.assertEqual(selection.product_name, "Pants Deportivo 3 Piezas")
        self.assertEqual(selection.talla, "16")
        self.assertEqual(selection.color, "Azul")


if __name__ == "__main__":
    unittest.main()
