"""Test del box de impresoras de etiqueta por tipo en la config del POS."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QPushButton

from pos_uniformes.services.label_printer_settings_cache_service import (
    load_label_printer_settings,
)
from pos_uniformes.ui.dialogs.settings_dialogs import _build_label_printers_box

_SDD = "pos_uniformes.services.label_printer_settings_cache_service.satellite_data_dir"


class PosLabelPrintersBoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_dos_combos_default_autodetectar(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                box = _build_label_printers_box(QDialog())
                combos = box.findChildren(QComboBox)
                self.assertEqual(len(combos), 2)
                self.assertEqual(combos[0].currentData(), "")  # autodetectar
                self.assertEqual(combos[1].currentData(), "")

    def test_guardar_persiste_seleccion(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                box = _build_label_printers_box(QDialog())
                combos = box.findChildren(QComboBox)
                # Simular impresoras disponibles y seleccionarlas.
                combos[0].addItem("Brother-Continua", "Brother-Continua")
                combos[0].setCurrentIndex(combos[0].count() - 1)
                combos[1].addItem("Brother-DK1221", "Brother-DK1221")
                combos[1].setCurrentIndex(combos[1].count() - 1)
                save_btn = box.findChildren(QPushButton)[0]
                with patch(
                    "pos_uniformes.ui.dialogs.settings_dialogs.QMessageBox.information"
                ):
                    save_btn.click()
                self.assertEqual(
                    load_label_printer_settings(),
                    ("Brother-Continua", "Brother-DK1221"),
                )

    def test_refleja_config_guardada(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                from pos_uniformes.services.label_printer_settings_cache_service import (
                    save_label_printer_settings,
                )

                # Guardar como nombres que el combo sí tendrá tras agregarlos.
                save_label_printer_settings("", "")
                box = _build_label_printers_box(QDialog())
                combos = box.findChildren(QComboBox)
                # Ambos en autodetectar porque la config es vacía.
                self.assertEqual(combos[0].currentData(), "")
                self.assertEqual(combos[1].currentData(), "")


if __name__ == "__main__":
    unittest.main()
