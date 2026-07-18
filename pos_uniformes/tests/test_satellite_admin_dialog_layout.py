"""Estructura del menú admin del satélite (Ctrl+Shift+A).

Rediseño 2026-07-08: de 5 secciones apiladas (saturado en pantalla táctil) a
pestañas — Conexión, Impresoras, Búsqueda, Conteos. Este test fija que las
pestañas existen y que ninguna sección se perdió.

Además: en rol "Estación" la config de impresoras se oculta (la PC no tiene
impresoras); en rol "Servidor de impresión" se muestra.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QGroupBox, QLabel, QTabWidget

import pos_uniformes.ui.dialogs.satellite_admin_dialog as admin
from pos_uniformes.services.print_routing_cache_service import (
    MODO_LOCAL,
    MODO_SATELITE,
    save_print_routing,
)

_SDD = "pos_uniformes.services.print_routing_cache_service.satellite_data_dir"


class AdminDialogTabsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _build_dialog(self):
        captured = {}

        def _fake_exec(self):
            captured["dialog"] = self
            return 0

        # Aísla el archivo de identidad del satélite en un temp (no ensuciar data/).
        with tempfile.TemporaryDirectory() as ident_dir:
            with patch.object(admin, "_prompt_pin", return_value=True), patch.object(
                admin.QDialog, "exec", _fake_exec
            ), patch(
                "pos_uniformes.services.satellite_identity_service.satellite_data_dir",
                return_value=Path(ident_dir),
            ):
                admin.open_satellite_admin_dialog(None)
        return captured["dialog"]

    def _build_dialog_con_rol(self, modo: str):
        with tempfile.TemporaryDirectory() as d:
            with patch(_SDD, return_value=Path(d)):
                save_print_routing(modo, "pc-test")
                return self._build_dialog()

    @staticmethod
    def _groupbox(dialog, title: str) -> QGroupBox | None:
        for gb in dialog.findChildren(QGroupBox):
            if gb.title() == title:
                return gb
        return None

    def test_dialog_has_expected_tabs(self) -> None:
        dialog = self._build_dialog()
        tabs = dialog.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        self.assertEqual(len(labels), 5)
        joined = " ".join(labels)
        for esperado in ("Conexión", "Impresoras", "Búsqueda", "Conteos", "Anuncios"):
            self.assertIn(esperado, joined)

    def test_all_sections_survive_the_redesign(self) -> None:
        dialog = self._build_dialog()
        titles = {gb.title() for gb in dialog.findChildren(QGroupBox)}
        self.assertIn("Estado de conexion", titles)
        self.assertIn("Cambiar conexion", titles)
        self.assertIn("Impresora de tickets", titles)
        self.assertIn("Impresoras de etiquetas", titles)
        self.assertIn("Meilisearch (busqueda rapida)", titles)
        self.assertIn("Nuevo anuncio", titles)
        self.assertIn("Anuncios activos", titles)
        self.assertIn("Este satélite", titles)
        self.assertIn("Satélites", titles)

    def test_selector_de_destinos_arranca_en_todos(self) -> None:
        from PyQt6.QtWidgets import QCheckBox

        dialog = self._build_dialog()
        # El checkbox "Mostrar en todos los satélites" existe y viene marcado.
        todos = [
            cb for cb in dialog.findChildren(QCheckBox)
            if "todos los satélites" in cb.text().lower()
        ]
        self.assertTrue(todos)
        self.assertTrue(todos[0].isChecked())

    def test_estacion_oculta_config_de_impresoras(self) -> None:
        dialog = self._build_dialog_con_rol(MODO_SATELITE)
        self.assertTrue(self._groupbox(dialog, "Impresora de tickets").isHidden())
        self.assertTrue(self._groupbox(dialog, "Impresoras de etiquetas").isHidden())
        # Y muestra el aviso de estación.
        avisos = [
            lbl for lbl in dialog.findChildren(QLabel)
            if "Estación" in lbl.text() and not lbl.isHidden()
        ]
        self.assertTrue(avisos)

    def test_servidor_muestra_config_de_impresoras(self) -> None:
        dialog = self._build_dialog_con_rol(MODO_LOCAL)
        self.assertFalse(self._groupbox(dialog, "Impresora de tickets").isHidden())
        self.assertFalse(self._groupbox(dialog, "Impresoras de etiquetas").isHidden())


if __name__ == "__main__":
    unittest.main()
