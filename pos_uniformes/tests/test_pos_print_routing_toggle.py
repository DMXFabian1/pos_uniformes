"""Test del toggle de modo de impresión en la config del POS principal."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QPushButton, QRadioButton

from pos_uniformes.services.print_routing_cache_service import (
    MODO_LOCAL,
    MODO_SATELITE,
    load_print_routing,
)
from pos_uniformes.ui.dialogs.settings_dialogs import _build_print_routing_box

_SDD = "pos_uniformes.services.print_routing_cache_service.satellite_data_dir"


class PosRoutingToggleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_refleja_default_local(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                box = _build_print_routing_box(QDialog())
                radios = box.findChildren(QRadioButton)
                self.assertTrue(radios[0].isChecked())   # local
                self.assertFalse(radios[1].isChecked())  # satélite

    def test_guardar_satelite_persiste(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                box = _build_print_routing_box(QDialog())
                radios = box.findChildren(QRadioButton)
                radios[1].setChecked(True)  # enviar al satélite
                save_btn = box.findChildren(QPushButton)[0]
                with patch(
                    "pos_uniformes.ui.dialogs.settings_dialogs.QMessageBox.information"
                ):
                    save_btn.click()
                self.assertEqual(load_print_routing()[0], MODO_SATELITE)

    def test_refleja_satelite_guardado(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                from pos_uniformes.services.print_routing_cache_service import (
                    save_print_routing,
                )

                save_print_routing(MODO_SATELITE, "kiosko")
                box = _build_print_routing_box(QDialog())
                radios = box.findChildren(QRadioButton)
                self.assertTrue(radios[1].isChecked())  # satélite marcado
                self.assertEqual(load_print_routing(), (MODO_SATELITE, "kiosko"))


if __name__ == "__main__":
    unittest.main()
