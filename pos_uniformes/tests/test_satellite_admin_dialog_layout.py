"""Estructura del menú admin del satélite (Ctrl+Shift+A).

Rediseño 2026-07-08: de 5 secciones apiladas (saturado en pantalla táctil) a
3 pestañas — Conexión, Impresoras, Búsqueda. Este test fija que las pestañas
existen y que ninguna sección se perdió en el rediseño.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QGroupBox, QTabWidget

import pos_uniformes.ui.dialogs.satellite_admin_dialog as admin


class AdminDialogTabsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _build_dialog(self):
        captured = {}

        def _fake_exec(self):
            captured["dialog"] = self
            return 0

        with patch.object(admin, "_prompt_pin", return_value=True), patch.object(
            admin.QDialog, "exec", _fake_exec
        ):
            admin.open_satellite_admin_dialog(None)
        return captured["dialog"]

    def test_dialog_has_three_tabs(self) -> None:
        dialog = self._build_dialog()
        tabs = dialog.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        self.assertEqual(len(labels), 3)
        joined = " ".join(labels)
        self.assertIn("Conexión", joined)
        self.assertIn("Impresoras", joined)
        self.assertIn("Búsqueda", joined)

    def test_all_five_sections_survive_the_redesign(self) -> None:
        dialog = self._build_dialog()
        titles = {gb.title() for gb in dialog.findChildren(QGroupBox)}
        self.assertIn("Estado de conexion", titles)
        self.assertIn("Cambiar conexion", titles)
        self.assertIn("Impresora de tickets", titles)
        self.assertIn("Impresoras de etiquetas", titles)
        self.assertIn("Meilisearch (busqueda rapida)", titles)


if __name__ == "__main__":
    unittest.main()
