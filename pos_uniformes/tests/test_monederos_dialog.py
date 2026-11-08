"""Administración de monederos (POS principal): arma la ventana y avisa
cuando el cashback no está configurado."""

from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.dialogs.monederos_dialog import MonederosDialog


class MonederosDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_sin_configurar_lo_dice(self):
        with patch.object(MonederosDialog, "_leer", return_value=None):
            dlg = MonederosDialog(None, usuario_id=1)
        self.assertIn("NO está configurado", dlg._config_estado.text())

    def test_muestra_la_tasa_vigente(self):
        from datetime import datetime, timezone

        with patch.object(MonederosDialog, "_leer", return_value=(Decimal("3.50"), True, datetime(2026, 11, 8, tzinfo=timezone.utc))):
            dlg = MonederosDialog(None, usuario_id=1)
        self.assertAlmostEqual(dlg._tasa.value(), 3.5)
        self.assertTrue(dlg._habilitado.isChecked())
        self.assertIn("3.50%", dlg._config_estado.text())


if __name__ == "__main__":
    unittest.main()
