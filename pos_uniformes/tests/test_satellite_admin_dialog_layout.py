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

from PyQt6.QtCore import Qt
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

    @staticmethod
    def _opciones(dialog) -> list[str]:
        menu = dialog.menu
        return [
            menu.item(i).text() for i in range(menu.count())
            if (menu.item(i).data(Qt.ItemDataRole.UserRole) or 0) >= 0
            and menu.item(i).flags() & Qt.ItemFlag.ItemIsEnabled
        ]

    def test_el_menu_lateral_trae_cada_seccion_con_su_nombre_completo(self) -> None:
        # Rediseño 2026-11-06: las 9 pestañas no cabían y se leían «…», «Im…»,
        # «Te…». Ahora es un menú a la izquierda, agrupado.
        dialog = self._build_dialog()
        opciones = self._opciones(dialog)
        self.assertEqual(len(opciones), 7)
        for esperado in ("Conexión y versión", "Impresoras", "Cámaras", "Búsqueda",
                         "Anuncios", "Temporada", "Mantenimiento"):
            self.assertTrue(any(esperado in o for o in opciones), (esperado, opciones))
        self.assertEqual(dialog.paginas.count(), 7)
        self.assertIsNone(dialog.findChild(QTabWidget))

    def test_cada_opcion_abre_su_pagina_y_los_letreros_no_se_eligen(self) -> None:
        dialog = self._build_dialog()
        menu, paginas = dialog.menu, dialog.paginas
        vistos = set()
        for fila in range(menu.count()):
            menu.setCurrentRow(fila)
            indice = menu.item(fila).data(Qt.ItemDataRole.UserRole)
            if indice >= 0:
                self.assertEqual(paginas.currentIndex(), indice)
                vistos.add(indice)
            else:
                self.assertFalse(menu.item(fila).flags() & Qt.ItemFlag.ItemIsEnabled)
        self.assertEqual(vistos, set(range(7)))

    def test_abre_en_conexion(self) -> None:
        dialog = self._build_dialog()
        self.assertIn("Conexión", dialog.menu.currentItem().text())
        self.assertEqual(dialog.paginas.currentIndex(), 0)

    def test_conteos_y_precios_bajaron_a_mantenimiento(self) -> None:
        dialog = self._build_dialog()
        fila = next(i for i in range(dialog.menu.count()) if "Mantenimiento" in dialog.menu.item(i).text())
        pagina = dialog.paginas.widget(dialog.menu.item(fila).data(Qt.ItemDataRole.UserRole))
        titulos = {gb.title() for gb in pagina.findChildren(QGroupBox)}
        self.assertEqual(titulos, {"Calendario de conteos", "Cambiar el precio de una prenda"})

    def test_la_conexion_es_una_sola_tarjeta_y_dice_la_version_de_verdad(self) -> None:
        with patch("pos_uniformes.utils.app_metadata.version_visible", return_value="6 nov · abc1234"):
            dialog = self._build_dialog()
        titles = {gb.title() for gb in dialog.findChildren(QGroupBox)}
        self.assertIn("Conexión con la PC principal", titles)
        self.assertNotIn("Estado de conexion", titles)       # repetía la misma IP
        textos = " ".join(lbl.text() for lbl in dialog.findChildren(QLabel))
        self.assertIn("6 nov · abc1234", textos)
        self.assertNotIn("2026.11.11", textos)

    def test_el_buzon_va_en_la_cabecera_y_no_es_una_pagina(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        dialog = self._build_dialog()
        boton = dialog.findChild(QPushButton, "adminBuzon")
        self.assertIsNotNone(boton)
        self.assertIn("Buzón", boton.text())
        self.assertFalse(any("Buzón" in o for o in self._opciones(dialog)))

    def test_all_sections_survive_the_redesign(self) -> None:
        dialog = self._build_dialog()
        titles = {gb.title() for gb in dialog.findChildren(QGroupBox)}
        self.assertIn("Conexión con la PC principal", titles)
        self.assertIn("Actualizaciones", titles)
        self.assertIn("Impresora de tickets", titles)
        self.assertIn("Impresoras de etiquetas", titles)
        self.assertIn("Meilisearch (busqueda rapida)", titles)
        self.assertIn("Nuevo anuncio", titles)
        self.assertIn("Anuncios activos", titles)
        self.assertIn("Este satélite", titles)
        self.assertIn("Satélites", titles)
        self.assertIn("DVR de cámaras", titles)

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
