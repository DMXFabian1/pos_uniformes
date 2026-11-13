"""Pestaña Inventario, tanda 2 «Limpieza» (2026-11-13): lo que se ve y lo que ya no."""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication, QMessageBox

from pos_uniformes.database.models import RolUsuario
from pos_uniformes.ui.main_window import MainWindow


def _cerrar(window: MainWindow) -> None:
    from PyQt6 import sip

    if sip.isdeleted(window):
        return
    window._force_close = True
    window.close()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    QApplication.processEvents()


class InventarioTanda2PantallaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self) -> MainWindow:
        window = MainWindow(user_id=1)
        self.addCleanup(_cerrar, window)
        return window

    def _encabezados(self, window: MainWindow) -> list[str]:
        tabla = window.inventory_table
        return [tabla.horizontalHeaderItem(i).text() for i in range(tabla.columnCount())]

    @staticmethod
    def _textos_menu(menu) -> list[str]:
        return [a.text() for a in menu.actions() if not a.isSeparator()]

    # ── QR fuera de la vista ──────────────────────────────────────────────

    def test_sin_nada_de_qr_en_la_pantalla(self) -> None:
        window = self._ventana()
        self.assertNotIn("QR", self._encabezados(window))
        for nombre in (
            "inventory_qr_filter_combo",
            "inventory_qr_pending_counter",
            "qr_preview_label",
            "qr_preview_info_label",
            "qr_status_label",
            "inventory_generate_qr_button",
        ):
            self.assertFalse(hasattr(window, nombre), nombre)

    def test_generar_qr_queda_en_mas_poco_usado(self) -> None:
        window = self._ventana()
        menu_mas = window.inventory_more_button.menu()
        submenus = {a.text(): a.menu() for a in menu_mas.actions() if a.menu() is not None}
        self.assertIn("Poco usado", submenus)
        self.assertEqual(
            self._textos_menu(submenus["Poco usado"]),
            ["Generar QR de la selección", "Generar los QR que faltan", "Regenerar todos los QR"],
        )
        # Fuera del submenú no queda ninguna acción de QR.
        self.assertFalse(any("QR" in t for t in self._textos_menu(menu_mas) if t != "Poco usado"))

    def test_alta_de_talla_ya_no_pregunta_por_el_qr(self) -> None:
        window = self._ventana()
        window.current_role = RolUsuario.ADMIN
        window._create_or_edit_presentation = Mock(return_value=("SKU-NUEVO", 7))
        window.refresh_all = Mock()
        window._set_combo_value = Mock()
        with patch.object(QMessageBox, "question") as pregunta, patch.object(QMessageBox, "information") as aviso:
            window._handle_create_variant()
        pregunta.assert_not_called()
        aviso.assert_called_once()
        self.assertNotIn("QR", aviso.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
