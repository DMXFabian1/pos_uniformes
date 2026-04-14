from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QMessageBox, QPushButton, QSpinBox, QTableWidget, QVBoxLayout, QWidget

from pos_uniformes.ui.dialogs.inventory_label_batch_dialog import _BatchQuantityTabNavigator, build_inventory_label_batch_dialog
from pos_uniformes.utils.label_generator import LabelRenderResult


class _DialogHost(QWidget):
    def _create_modal_dialog(
        self,
        title: str,
        helper_text: str | None = None,
        width: int = 460,
        *,
        expand_to_screen: bool = False,
    ) -> tuple[QDialog, QVBoxLayout]:
        layout = QVBoxLayout()
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(width)
        dialog.setLayout(layout)
        return dialog, layout


class InventoryLabelBatchDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_batch_dialog_prints_only_rows_with_requested_quantity(self) -> None:
        host = _DialogHost()
        contexts = [
            SimpleNamespace(variant_id=1, sku="SKU-001", product_name="Pants", talla="14", color="Azul"),
            SimpleNamespace(variant_id=2, sku="SKU-002", product_name="Camisa", talla="16", color="Blanco"),
        ]
        render_calls: list[tuple[int, str, int]] = []
        print_calls: list[tuple[str, int]] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "label.png"
            image_path.write_bytes(b"not-a-real-png")

            def render_label(variant_id: int, mode: str, requested_copies: int) -> LabelRenderResult:
                render_calls.append((variant_id, mode, requested_copies))
                return LabelRenderResult(
                    mode=mode,
                    image_path=image_path,
                    effective_copies=requested_copies,
                    requested_copies=requested_copies,
                )

            def print_label(image_path: Path, copies: int, sku: str, _dialog: QDialog | None) -> bool:
                print_calls.append((sku, copies))
                return True

            def fake_exec(dialog: QDialog) -> int:
                table = dialog.findChild(QTableWidget, "inventoryLabelBatchTable")
                self.assertIsNotNone(table)
                first_spin = table.cellWidget(0, 4)
                second_spin = table.cellWidget(1, 4)
                self.assertIsInstance(first_spin, QSpinBox)
                self.assertIsInstance(second_spin, QSpinBox)
                first_spin.setValue(2)
                second_spin.setValue(0)
                print_button = next(button for button in dialog.findChildren(QPushButton) if button.text() == "Imprimir lote")
                print_button.click()
                return int(QDialog.DialogCode.Rejected)

            with patch("pos_uniformes.ui.dialogs.inventory_label_batch_dialog.QDialog.exec", new=fake_exec), patch.object(
                QMessageBox,
                "information",
            ) as information_mock:
                build_inventory_label_batch_dialog(
                    host,
                    contexts=contexts,
                    render_label=render_label,
                    print_label=print_label,
                )

        self.assertEqual(render_calls, [(1, "standard", 2)])
        self.assertEqual(print_calls, [("SKU-001", 2)])
        information_mock.assert_called_once()

    def test_batch_dialog_sets_tab_order_through_mode_quantities_and_actions(self) -> None:
        host = _DialogHost()
        contexts = [
            SimpleNamespace(variant_id=1, sku="SKU-001", product_name="Pants", talla="14", color="Azul"),
            SimpleNamespace(variant_id=2, sku="SKU-002", product_name="Camisa", talla="16", color="Blanco"),
        ]
        tab_calls: list[tuple[QWidget, QWidget]] = []

        def fake_exec(_dialog: QDialog) -> int:
            return int(QDialog.DialogCode.Rejected)

        def fake_set_tab_order(previous: QWidget, next_widget: QWidget) -> None:
            tab_calls.append((previous, next_widget))

        with (
            patch("pos_uniformes.ui.dialogs.inventory_label_batch_dialog.QDialog.exec", new=fake_exec),
            patch("pos_uniformes.ui.dialogs.inventory_label_batch_dialog.QWidget.setTabOrder", new=fake_set_tab_order),
        ):
            build_inventory_label_batch_dialog(
                host,
                contexts=contexts,
                render_label=lambda variant_id, mode, requested_copies: LabelRenderResult(
                    mode=mode,
                    image_path=Path("/tmp/label.png"),
                    effective_copies=requested_copies,
                    requested_copies=requested_copies,
                ),
                print_label=lambda image_path, copies, sku, dialog: True,
            )

        self.assertEqual(len(tab_calls), 4)
        self.assertEqual(tab_calls[0][0].metaObject().className(), "QComboBox")
        self.assertIsInstance(tab_calls[0][1], QSpinBox)
        self.assertIsInstance(tab_calls[1][0], QSpinBox)
        self.assertIsInstance(tab_calls[1][1], QSpinBox)
        self.assertIsInstance(tab_calls[2][0], QSpinBox)
        self.assertIsInstance(tab_calls[2][1], QPushButton)
        self.assertEqual(tab_calls[2][1].text(), "Cerrar")
        self.assertIsInstance(tab_calls[3][0], QPushButton)
        self.assertEqual(tab_calls[3][0].text(), "Cerrar")
        self.assertIsInstance(tab_calls[3][1], QPushButton)
        self.assertEqual(tab_calls[3][1].text(), "Imprimir lote")

    def test_tab_navigator_moves_focus_forward_and_backward_between_quantities(self) -> None:
        dialog = QDialog()
        mode_combo = QComboBox(dialog)
        mode_combo.addItem("Normal", "standard")
        first_spin = QSpinBox(dialog)
        second_spin = QSpinBox(dialog)
        close_button = QPushButton("Cerrar", dialog)
        print_button = QPushButton("Imprimir lote", dialog)
        navigator = _BatchQuantityTabNavigator(
            mode_combo=mode_combo,
            quantity_spins=[first_spin, second_spin],
            close_button=close_button,
            print_button=print_button,
        )

        line_edit = first_spin.lineEdit()
        self.assertIsNotNone(line_edit)
        focus_calls: list[tuple[str, Qt.FocusReason]] = []
        original_second_focus = second_spin.setFocus
        second_spin.setFocus = lambda reason=Qt.FocusReason.OtherFocusReason: focus_calls.append(("second", reason))
        original_second_select_all = second_spin.lineEdit().selectAll if second_spin.lineEdit() is not None else None
        if second_spin.lineEdit() is not None:
            second_spin.lineEdit().selectAll = lambda: focus_calls.append(("second_select_all", Qt.FocusReason.OtherFocusReason))
        handled_forward = navigator.eventFilter(
            line_edit,
            QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Tab), Qt.KeyboardModifier.NoModifier),
        )
        second_spin.setFocus = original_second_focus
        if second_spin.lineEdit() is not None and original_second_select_all is not None:
            second_spin.lineEdit().selectAll = original_second_select_all
        self.assertTrue(handled_forward)
        self.assertIn(("second", Qt.FocusReason.TabFocusReason), focus_calls)
        self.assertIn(("second_select_all", Qt.FocusReason.OtherFocusReason), focus_calls)

        second_line_edit = second_spin.lineEdit()
        self.assertIsNotNone(second_line_edit)
        backward_calls: list[tuple[str, Qt.FocusReason]] = []
        original_first_focus = first_spin.setFocus
        first_spin.setFocus = lambda reason=Qt.FocusReason.OtherFocusReason: backward_calls.append(("first", reason))
        original_first_select_all = first_spin.lineEdit().selectAll if first_spin.lineEdit() is not None else None
        if first_spin.lineEdit() is not None:
            first_spin.lineEdit().selectAll = lambda: backward_calls.append(("first_select_all", Qt.FocusReason.OtherFocusReason))
        handled_backward = navigator.eventFilter(
            second_line_edit,
            QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Backtab), Qt.KeyboardModifier.ShiftModifier),
        )
        first_spin.setFocus = original_first_focus
        if first_spin.lineEdit() is not None and original_first_select_all is not None:
            first_spin.lineEdit().selectAll = original_first_select_all
        self.assertTrue(handled_backward)
        self.assertIn(("first", Qt.FocusReason.TabFocusReason), backward_calls)
        self.assertIn(("first_select_all", Qt.FocusReason.OtherFocusReason), backward_calls)


if __name__ == "__main__":
    unittest.main()
