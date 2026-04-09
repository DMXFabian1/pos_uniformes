from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from pos_uniformes.services.inventory_count_service import InventoryCountRow, InventoryCountVariantView
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
        self.assertFalse(dialog.initial_context_label.isVisible())

    def test_dialog_starts_without_batch_row_selected(self) -> None:
        dialog = InventoryCountDialog(
            initial_rows=[
                InventoryCountRow(
                    variante_id=11,
                    sku="SKU000011",
                    producto_nombre="Bata",
                    stock_sistema=9,
                    stock_contado=9,
                    delta=0,
                )
            ],
            initial_context_label="Filas seleccionadas (1)",
        )

        self.assertEqual(dialog.batch_table.currentRow(), -1)
        self.assertFalse(dialog.batch_table.selectionModel().hasSelection())

    def test_escape_clears_batch_table_selection(self) -> None:
        dialog = InventoryCountDialog(
            initial_rows=[
                InventoryCountRow(
                    variante_id=11,
                    sku="SKU000011",
                    producto_nombre="Bata",
                    stock_sistema=9,
                    stock_contado=9,
                    delta=0,
                )
            ],
            initial_context_label="Filas seleccionadas (1)",
        )
        dialog.show()
        dialog.batch_table.selectRow(0)
        dialog.batch_table.setFocus()

        QTest.keyClick(dialog.batch_table, Qt.Key.Key_Escape)

        self.assertEqual(dialog.batch_table.currentRow(), -1)
        self.assertFalse(dialog.batch_table.selectionModel().hasSelection())

    def test_escape_from_batch_count_spin_returns_focus_to_sku_input(self) -> None:
        dialog = InventoryCountDialog(
            initial_rows=[
                InventoryCountRow(
                    variante_id=11,
                    sku="SKU000011",
                    producto_nombre="Bata",
                    stock_sistema=9,
                    stock_contado=9,
                    delta=0,
                )
            ],
            initial_context_label="Filas seleccionadas (1)",
        )
        dialog.show()
        counted_spin = dialog.batch_table.cellWidget(0, 3)
        self.assertIsNotNone(counted_spin)
        counted_line_edit = counted_spin.lineEdit()
        self.assertIsNotNone(counted_line_edit)
        dialog.batch_table.selectRow(0)
        counted_line_edit.setFocus()

        QTest.keyClick(counted_line_edit, Qt.Key.Key_Escape)
        QTest.qWait(20)

        self.assertFalse(dialog.batch_table.selectionModel().hasSelection())
        self.assertEqual(dialog.batch_table.currentRow(), -1)
        self.assertTrue(dialog.sku_input.hasFocus())


if __name__ == "__main__":
    unittest.main()
