from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.login_dialog import LoginDialog


class LoginDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @patch.object(LoginDialog, "_load_user_options")
    def test_loading_state_disables_login_controls(self, _load_user_options) -> None:
        dialog = LoginDialog()
        dialog.show()
        self.app.processEvents()
        dialog.user_combo.addItem("Administrador", "admin")
        dialog.login_button.setEnabled(True)

        dialog.set_loading_state("Cargando aplicacion...")

        self.assertTrue(dialog.status_label.isVisible())
        self.assertEqual(dialog.status_label.text(), "Cargando aplicacion...")
        self.assertFalse(dialog.user_combo.isEnabled())
        self.assertFalse(dialog.password_input.isEnabled())
        self.assertFalse(dialog.password_toggle_button.isEnabled())
        self.assertFalse(dialog.login_button.isEnabled())
        self.assertFalse(dialog.cancel_button.isEnabled())

        dialog.clear_loading_state()

        self.assertTrue(dialog.user_combo.isEnabled())
        self.assertTrue(dialog.password_input.isEnabled())
        self.assertTrue(dialog.password_toggle_button.isEnabled())
        self.assertTrue(dialog.login_button.isEnabled())
        self.assertTrue(dialog.cancel_button.isEnabled())

    @patch.object(LoginDialog, "_load_user_options")
    def test_reject_is_ignored_while_loading(self, _load_user_options) -> None:
        dialog = LoginDialog()
        dialog.show()
        self.app.processEvents()

        dialog.set_loading_state("Cargando aplicacion...")
        dialog.reject()
        self.app.processEvents()

        self.assertTrue(dialog.isVisible())

        dialog.clear_loading_state()
        dialog.reject()
        self.app.processEvents()

        self.assertFalse(dialog.isVisible())

    @patch.object(LoginDialog, "_load_user_options")
    def test_stylesheet_keeps_combo_popup_text_dark_by_default(self, _load_user_options) -> None:
        dialog = LoginDialog()
        stylesheet = dialog.styleSheet()

        self.assertIn("selection-color: #f9f4ea;", stylesheet)
        self.assertNotIn("selection-background-color: #8f4527;\n                color: #f9f4ea;", stylesheet)


if __name__ == "__main__":
    unittest.main()
