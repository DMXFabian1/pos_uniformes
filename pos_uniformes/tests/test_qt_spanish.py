"""La traducción de Qt deja los botones estándar en español.

Sin ella, todo QMessageBox con StandardButton (Yes/No/Cancel) salía en
inglés aunque la app entera esté en español.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox

from pos_uniformes.utils.qt_spanish import instalar_espanol_qt


class QtEspanolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_botones_estandar_en_espanol(self) -> None:
        self.assertTrue(instalar_espanol_qt(self.app))
        box = QMessageBox(
            QMessageBox.Icon.Question,
            "t",
            "m",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        textos = {b.text().replace("&", "") for b in box.buttons()}
        self.assertEqual(textos, {"Sí", "No", "Cancelar"})


if __name__ == "__main__":
    unittest.main()
