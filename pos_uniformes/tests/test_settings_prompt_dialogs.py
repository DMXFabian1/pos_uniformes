from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from pos_uniformes.database.models import RolUsuario
from pos_uniformes.ui.dialogs.settings_prompt_dialogs import (
    prompt_client_data,
    prompt_create_user_data,
    prompt_role_change,
    prompt_supplier_data,
)


class SettingsPromptDialogsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_create_user_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.settings_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(prompt_create_user_data(QWidget()))

    def test_role_change_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.settings_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(prompt_role_change(QWidget(), RolUsuario.ADMIN))

    def test_supplier_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.settings_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(
                prompt_supplier_data(
                    QWidget(),
                    title="Proveedor",
                    helper_text="Captura proveedor.",
                )
            )

    def test_client_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.settings_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(
                prompt_client_data(
                    QWidget(),
                    title="Cliente",
                    helper_text="Captura cliente.",
                )
            )


if __name__ == "__main__":
    unittest.main()
