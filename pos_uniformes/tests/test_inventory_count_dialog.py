from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.services.inventory_count_service import InventoryCountVariantView
from pos_uniformes.ui.dialogs.inventory_count_dialog import InventoryCountDialog


@contextmanager
def _fake_session_context():
    yield object()


class InventoryCountDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_lookup_sku_accumulates_count_when_dialog_starts_without_initial_rows(self) -> None:
        variant = InventoryCountVariantView(
            variante_id=11,
            sku="SKU000011",
            producto_nombre="Bata",
            talla="12",
            color="Blanca",
            escuela_nombre="General",
            stock_actual=9,
        )
        dialog = InventoryCountDialog()

        with (
            patch("pos_uniformes.ui.dialogs.inventory_count_dialog.get_session", _fake_session_context),
            patch(
                "pos_uniformes.ui.dialogs.inventory_count_dialog.load_inventory_count_variant_by_sku",
                return_value=variant,
            ),
        ):
            dialog.sku_input.setText("SKU000011")
            dialog._handle_lookup_sku()
            dialog.sku_input.setText("SKU000011")
            dialog._handle_lookup_sku()

        self.assertEqual(len(dialog._rows), 1)
        self.assertEqual(dialog._rows[0].stock_contado, 2)
        self.assertEqual(dialog.batch_table.rowCount(), 1)
        self.assertIn("escaneo acumulado", dialog.initial_context_label.text().lower())


if __name__ == "__main__":
    unittest.main()
