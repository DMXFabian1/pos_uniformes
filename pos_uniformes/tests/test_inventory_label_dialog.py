from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from pos_uniformes.ui.dialogs.inventory_label_dialog import build_inventory_label_dialog
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


class InventoryLabelDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_build_inventory_label_dialog_renders_initial_preview_before_exec(self) -> None:
        host = _DialogHost()
        render_calls: list[tuple[str, int]] = []
        captured: dict[str, QDialog] = {}
        contexts = {
            1: SimpleNamespace(
                variant_id=1,
                sku="SKU-001",
                product_name="Pants Deportivo",
                talla="14",
                color="Azul Marino",
            ),
            2: SimpleNamespace(
                variant_id=2,
                sku="SKU-002",
                product_name="Pants Deportivo",
                talla="16",
                color="Negro",
            ),
        }
        dialog_variant_state = {"variant_id": 1}
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "label.png"
            image_path.write_bytes(b"not-a-real-png")

            def render_label(mode: str, requested_copies: int) -> LabelRenderResult:
                render_calls.append((mode, requested_copies))
                return LabelRenderResult(
                    mode=mode,
                    image_path=image_path,
                    effective_copies=requested_copies,
                    requested_copies=requested_copies,
                )

            def load_context(variant_id: int):
                dialog_variant_state["variant_id"] = variant_id
                return contexts[variant_id]

            def fake_exec(dialog: QDialog) -> int:
                captured["dialog"] = dialog
                return int(QDialog.DialogCode.Rejected)

            with patch("pos_uniformes.ui.dialogs.inventory_label_dialog.QDialog.exec", new=fake_exec):
                build_inventory_label_dialog(
                    host,
                    initial_context=contexts[1],
                    variant_ids=[1, 2],
                    current_index=0,
                    load_context=load_context,
                    render_label=render_label,
                    print_label=lambda _path, _copies, _sku, _dialog: True,
                )

        self.assertEqual(render_calls, [("standard", 1)])
        dialog = captured["dialog"]
        preview_label = dialog.findChild(QLabel, "inventoryLabelPreviewImage")
        self.assertIsNotNone(preview_label)
        self.assertGreaterEqual(preview_label.minimumWidth(), 640)
        mode_hint = dialog.findChild(QLabel, "inventoryLabelModeHint")
        self.assertIsNotNone(mode_hint)
        self.assertIn("etiqueta por pieza", mode_hint.text())
        print_button = dialog.findChild(QPushButton, "primaryButton")
        self.assertIsNotNone(print_button)
        self.assertEqual(print_button.text(), "Imprimir etiqueta")
        next_button = next(button for button in dialog.findChildren(QPushButton) if button.text() == "Siguiente")
        next_button.click()
        self.assertEqual(dialog_variant_state["variant_id"], 2)
        self.assertEqual(render_calls, [("standard", 1), ("standard", 1)])
        self.assertIn("SKU-002", dialog.findChild(QLabel, "inventoryMetaCard").text())


if __name__ == "__main__":
    unittest.main()
