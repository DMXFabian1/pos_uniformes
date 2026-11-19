"""Clic derecho en «Por prenda» (2026-11-19): el mismo menú y las mismas
acciones que «Por talla». Una prenda elige todas sus tallas; una talla
desplegada, solo esa."""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint
from PyQt6.QtWidgets import QApplication

from pos_uniformes.database.models import RolUsuario
from pos_uniformes.ui.helpers.inventory_context_menu_helper import (
    ACCION_CORREGIR_LOTE,
    build_inventory_context_menu_actions,
)
from pos_uniformes.ui.main_window import MainWindow
from tests.test_inventario_tanda4_pantalla import FILAS

MENU = "pos_uniformes.ui.helpers.inventario_pantalla.prompt_inventory_context_action"


def _cerrar(window: MainWindow) -> None:
    from PyQt6 import sip

    if sip.isdeleted(window):
        return
    window._force_close = True
    window.close()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    QApplication.processEvents()


class MenuContextualPorPrendaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self, *, rol: RolUsuario = RolUsuario.ADMIN) -> MainWindow:
        window = MainWindow(user_id=1)
        self.addCleanup(_cerrar, window)
        filas = [dict(f) for f in FILAS]
        for fila in filas:
            window.inventory_variant_combo.addItem(fila["sku"], fila["variante_id"])
        window.inventory_variant_combo.setCurrentIndex(-1)
        window._load_inventory_snapshot_rows = Mock(return_value=filas)
        # La fila de catálogo (de ahí sale «Activar/Desactivar»): la talla 8 está apagada.
        catalogo = [{**f, "variante_activo": f["variante_id"] != 3} for f in filas]
        window._load_catalog_snapshot_rows = Mock(return_value=catalogo)
        window.catalog_filtered_rows = catalogo
        window._refresh_inventory_overview = Mock()
        window.current_role = rol
        window._refresh_inventory_table()
        window.resize(1366, 768)
        for i in range(window.tabs.count()):
            if window.tabs.tabText(i).strip() == "Inventario":
                window.tabs.setCurrentIndex(i)
        window.show()
        window.inventario_pantalla.segmento[1].click()
        for _ in range(3):
            QApplication.processEvents()
        return window

    @staticmethod
    def _clic_derecho(arbol, indice) -> QPoint:
        punto = arbol.visualRect(indice).center()
        arbol.customContextMenuRequested.emit(punto)
        return punto

    def test_el_arbol_pide_menu_propio(self) -> None:
        window = self._ventana()
        from PyQt6.QtCore import Qt

        arbol = window.inventario_pantalla.prendas
        self.assertEqual(arbol.contextMenuPolicy(), Qt.ContextMenuPolicy.CustomContextMenu)

    def test_clic_derecho_en_prenda_elige_todas_sus_tallas_y_abre_el_menu_de_lote(self) -> None:
        window = self._ventana()
        arbol = window.inventario_pantalla.prendas
        window._handle_inventory_print_label = Mock()
        with patch(MENU, return_value="print") as menu:
            self._clic_derecho(arbol, arbol.modelo.index(0, 0))  # Pants · 4 tallas
        self.assertEqual(sorted(window._selected_inventory_variant_ids()), [1, 2, 3, 4])
        self.assertEqual(arbol.llaves_elegidas(), {arbol.modelo.grupos[0].llave})
        menu.assert_called_once()
        self.assertEqual(
            menu.call_args.kwargs["action_specs"],
            build_inventory_context_menu_actions(is_admin=True, variante_activa=True, tallas_elegidas=4),
        )
        window._handle_inventory_print_label.assert_called_once_with()

    def test_clic_derecho_en_prenda_reemplaza_lo_que_habia_elegido(self) -> None:
        window = self._ventana()
        arbol = window.inventario_pantalla.prendas
        with patch(MENU, return_value=None):
            self._clic_derecho(arbol, arbol.modelo.index(0, 0))
            self._clic_derecho(arbol, arbol.modelo.index(1, 0))  # Bata · Azul cielo (2 tallas)
        self.assertEqual(sorted(window._selected_inventory_variant_ids()), [5, 6])

    def test_corregir_existencias_de_una_prenda_va_al_lote_de_siempre(self) -> None:
        window = self._ventana()
        arbol = window.inventario_pantalla.prendas
        window._handle_inventory_bulk_adjustment = Mock()
        window._handle_inventory_adjustment = Mock()
        with patch(MENU, return_value=ACCION_CORREGIR_LOTE):
            self._clic_derecho(arbol, arbol.modelo.index(1, 0))
        window._handle_inventory_bulk_adjustment.assert_called_once_with()
        window._handle_inventory_adjustment.assert_not_called()

    def test_acciones_de_una_talla_no_corren_con_varias_elegidas(self) -> None:
        window = self._ventana()
        arbol = window.inventario_pantalla.prendas
        window._handle_update_variant = Mock()
        window._handle_toggle_variant = Mock()
        window._handle_purchase = Mock()
        window._handle_inventory_adjustment = Mock()
        for llave in ("edit", "entry", "adjust", "toggle"):
            with patch(MENU, return_value=llave):
                self._clic_derecho(arbol, arbol.modelo.index(0, 0))
        for manejador in ("_handle_update_variant", "_handle_toggle_variant", "_handle_purchase", "_handle_inventory_adjustment"):
            getattr(window, manejador).assert_not_called()

    def test_clic_derecho_en_talla_desplegada_elige_solo_esa_con_el_menu_de_por_talla(self) -> None:
        window = self._ventana()
        arbol = window.inventario_pantalla.prendas
        prenda = arbol.modelo.index(0, 0)
        arbol.setExpanded(prenda, True)
        QApplication.processEvents()
        window._handle_toggle_variant = Mock()
        with patch(MENU, return_value="toggle") as menu:
            self._clic_derecho(arbol, arbol.modelo.index(2, 0, prenda))  # talla 8, desactivada
        self.assertEqual(window._selected_inventory_variant_ids(), [3])
        self.assertEqual(window.inventory_variant_combo.currentData(), 3)
        self.assertEqual(
            menu.call_args.kwargs["action_specs"],
            build_inventory_context_menu_actions(is_admin=True, variante_activa=False),
        )
        window._handle_toggle_variant.assert_called_once_with()

    def test_talla_desplegada_editar_usa_el_manejador_de_siempre(self) -> None:
        window = self._ventana()
        arbol = window.inventario_pantalla.prendas
        prenda = arbol.modelo.index(0, 0)
        arbol.setExpanded(prenda, True)
        QApplication.processEvents()
        window._handle_update_variant = Mock()
        with patch(MENU, return_value="edit") as menu:
            self._clic_derecho(arbol, arbol.modelo.index(3, 0, prenda))  # talla 10
        self.assertEqual(
            menu.call_args.kwargs["action_specs"],
            build_inventory_context_menu_actions(is_admin=True, variante_activa=True),
        )
        window._handle_update_variant.assert_called_once_with()

    def test_cajero_en_talla_desplegada_no_corre_lo_apagado_y_si_imprime(self) -> None:
        window = self._ventana(rol=RolUsuario.CAJERO)
        arbol = window.inventario_pantalla.prendas
        prenda = arbol.modelo.index(0, 0)
        arbol.setExpanded(prenda, True)
        QApplication.processEvents()
        window._handle_update_variant = Mock()
        window._handle_inventory_print_label = Mock()
        with patch(MENU, return_value="edit") as menu:
            self._clic_derecho(arbol, arbol.modelo.index(3, 0, prenda))  # talla 10
        self.assertEqual(
            menu.call_args.kwargs["action_specs"],
            build_inventory_context_menu_actions(is_admin=False, variante_activa=True),
        )
        window._handle_update_variant.assert_not_called()
        with patch(MENU, return_value="print"):
            self._clic_derecho(arbol, arbol.modelo.index(3, 0, prenda))
        window._handle_inventory_print_label.assert_called_once_with()

    def test_cajero_no_imprime_etiquetas_de_una_prenda_completa(self) -> None:
        # Como la barra de lote: imprimir varias etiquetas es solo de ADMIN.
        window = self._ventana(rol=RolUsuario.CAJERO)
        window._refresh_permissions()
        arbol = window.inventario_pantalla.prendas
        window._handle_inventory_print_label = Mock()
        with patch(MENU, return_value="print") as menu:
            self._clic_derecho(arbol, arbol.modelo.index(0, 0))  # Pants · 4 tallas
        especificaciones = menu.call_args.kwargs["action_specs"]
        self.assertEqual([a.key for a in especificaciones if a.enabled], [])
        self.assertFalse(window.inventario_pantalla.barra_lote.etiquetas.isEnabled())
        window._handle_inventory_print_label.assert_not_called()

    def test_clic_derecho_real_en_talla_desplegada_abre_el_menu_una_vez(self) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QContextMenuEvent
        from PyQt6.QtTest import QTest

        window = self._ventana()
        arbol = window.inventario_pantalla.prendas
        prenda = arbol.modelo.index(0, 0)
        arbol.setExpanded(prenda, True)
        QApplication.processEvents()
        punto = arbol.visualRect(arbol.modelo.index(3, 2, prenda)).center()  # talla 10, columna 2
        sku = arbol.modelo.data(arbol.modelo.index(3, 0, prenda))
        esperado = next(f["variante_id"] for f in FILAS if f["sku"] == sku)
        with patch(MENU, return_value=None) as menu:
            QTest.mousePress(arbol.viewport(), Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, punto)
            evento = QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse, punto, arbol.viewport().mapToGlobal(punto)
            )
            QApplication.sendEvent(arbol.viewport(), evento)
            QTest.mouseRelease(arbol.viewport(), Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, punto)
            QApplication.processEvents()
        menu.assert_called_once()
        self.assertEqual(window._selected_inventory_variant_ids(), [esperado])

    def test_clic_derecho_fuera_de_las_filas_no_abre_nada(self) -> None:
        window = self._ventana()
        arbol = window.inventario_pantalla.prendas
        with patch(MENU) as menu:
            arbol.customContextMenuRequested.emit(QPoint(5, arbol.viewport().height() - 2))
        menu.assert_not_called()


if __name__ == "__main__":
    unittest.main()
