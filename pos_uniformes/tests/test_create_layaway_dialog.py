from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QWidget

from pos_uniformes.ui.dialogs.create_layaway_dialog import build_create_layaway_dialog


class _DialogHost(QWidget):
    def _create_modal_dialog(
        self,
        title: str,
        helper_text: str | None = None,
        width: int = 460,
        *,
        expand_to_screen: bool = False,
    ) -> tuple[QDialog, QVBoxLayout]:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(width)
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        return dialog, layout


class CreateLayawayDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_returns_none_when_cancelled(self) -> None:
        host = _DialogHost()
        with patch("pos_uniformes.ui.dialogs.create_layaway_dialog.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(
                build_create_layaway_dialog(
                    host,
                    initial_items=[],
                    selected_catalog_row=None,
                )
            )


if __name__ == "__main__":
    unittest.main()
