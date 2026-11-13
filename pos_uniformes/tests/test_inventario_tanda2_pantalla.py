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

    # ── Sin Apartado ni Estado; la desactivada en gris ──────────────────

    def test_sin_columnas_apartado_ni_estado(self) -> None:
        encabezados = self._encabezados(self._ventana())
        self.assertNotIn("Apartado", encabezados)
        self.assertNotIn("Estado", encabezados)

    def test_desactivada_se_pinta_en_gris_con_aviso(self) -> None:
        from pos_uniformes.ui.helpers.inventory_table_row_helper import build_inventory_table_row_views

        window = self._ventana()
        fila = {
            "variante_id": 3, "sku": "SKU-3", "producto_nombre_base": "Pants", "talla": "10", "color": "Azul",
            "stock_actual": 4, "variante_activa": False, "ultimo_conteo_at": None, "stock_minimo": None,
        }
        vistas = build_inventory_table_row_views([fila])
        window.inventory_table.setRowCount(1)
        window._populate_inventory_table_rows(vistas)
        celda = window.inventory_table.item(0, 1)
        self.assertIn("Desactivada", celda.toolTip())
        self.assertEqual(celda.foreground().color().name(), "#7a6d60")

    # ── «Dónde» junta Piso y Almacén ────────────────────────────────────

    def test_donde_en_una_columna_con_el_reparto_al_pasar_el_mouse(self) -> None:
        from pos_uniformes.ui.helpers.inventory_table_row_helper import build_inventory_table_row_views

        window = self._ventana()
        encabezados = self._encabezados(window)
        self.assertIn("Dónde", encabezados)
        self.assertNotIn("Piso", encabezados)
        self.assertNotIn("Almacén", encabezados)
        fila = {
            "variante_id": 4, "sku": "SKU-4", "producto_nombre_base": "Pants", "talla": "10", "color": "Azul",
            "stock_actual": 12, "stock_bodega": 6, "stock_piso": 2, "variante_activa": True,
            "ultimo_conteo_at": None, "stock_minimo": None,
        }
        window.inventory_table.setRowCount(1)
        window._populate_inventory_table_rows(build_inventory_table_row_views([fila]))
        columna = encabezados.index("Dónde")
        celda = window.inventory_table.item(0, columna)
        self.assertEqual(celda.text(), "Bodega 6 · Piso 2")
        self.assertEqual(celda.toolTip(), "Tienda 4 · Bodega 6 · Piso 2")

    # ── Precio con su oferta ────────────────────────────────────────────

    def test_columna_precio_con_oferta_y_precio_normal_al_pasar_el_mouse(self) -> None:
        from decimal import Decimal

        from pos_uniformes.ui.helpers.inventory_table_row_helper import build_inventory_table_row_views

        window = self._ventana()
        encabezados = self._encabezados(window)
        columna = encabezados.index("Precio")
        fila = {
            "variante_id": 5, "sku": "SKU-5", "producto_nombre_base": "Pants", "talla": "10", "color": "Azul",
            "stock_actual": 2, "variante_activa": True, "ultimo_conteo_at": None, "stock_minimo": None,
            "precio_venta": Decimal("250"), "rebaja_tipo": "oferta", "rebaja_precio": Decimal("175"),
        }
        window.inventory_table.setRowCount(1)
        window._populate_inventory_table_rows(build_inventory_table_row_views([fila]))
        celda = window.inventory_table.item(0, columna)
        self.assertEqual(celda.text(), "Oferta $175")
        self.assertEqual(celda.toolTip(), "Precio normal $250")

    def test_al_cerrar_ofertas_se_refresca_el_listado(self) -> None:
        window = self._ventana()
        window.current_role = RolUsuario.ADMIN
        window._invalidate_listing_snapshot_caches = Mock()
        window._handle_inventory_filters_changed = Mock()
        with patch("pos_uniformes.ui.dialogs.rebajas_dialog.RebajasDialog") as dialogo:
            window._handle_open_rebajas()
        dialogo.return_value.exec.assert_called_once()
        window._invalidate_listing_snapshot_caches.assert_called_once_with(catalog=False, inventory=True)
        window._handle_inventory_filters_changed.assert_called_once_with()

    # ── Sin ayuda fija, sin filtros de la importación vieja ─────────────

    def test_sin_linea_de_ayuda_ni_filtros_viejos(self) -> None:
        from PyQt6.QtWidgets import QLabel

        window = self._ventana()
        self.assertFalse(hasattr(window, "inventory_origin_filter_combo"))
        self.assertFalse(hasattr(window, "inventory_duplicate_filter_combo"))
        pestana = window.inventory_table.window()
        textos = [lbl.text() for lbl in pestana.findChildren(QLabel)]
        self.assertFalse(any(t.startswith("Ctrl/Cmd + clic") for t in textos))
        self.assertIn("Ctrl/Cmd + clic", window.inventory_table.toolTip())

    # ── Acentos y palabras de la tienda ─────────────────────────────────

    def test_palabras_de_la_tienda(self) -> None:
        from PyQt6.QtWidgets import QGroupBox

        window = self._ventana()
        titulos = {g.title() for g in window.findChildren(QGroupBox)}
        self.assertTrue({"Acciones rápidas", "Selección actual", "Tallas"} <= titulos, titulos)
        self.assertFalse({"Acciones rapidas", "Seleccion actual", "Presentaciones disponibles"} & titulos)
        self.assertEqual(
            self._encabezados(window), ["SKU", "Prenda", "Talla", "Color", "Hay", "Dónde", "Precio", "Contada"]
        )
        self.assertEqual(window.inventory_status_badge.text(), "Sin selección")
        menus = [
            window.inventory_new_button.menu(),
            window.inventory_edit_button.menu(),
            window.inventory_stock_button.menu(),
            window.inventory_labels_button.menu(),
            window.inventory_more_button.menu(),
        ]
        textos = " ".join(t for m in menus for t in self._textos_menu(m))
        for jerga in ("presentacion", "Presentacion", "fisico", "Categoria", "seleccion", "masivo", "stock"):
            self.assertNotIn(jerga, textos)

    def test_ficha_no_se_corta_a_1366(self) -> None:
        from PyQt6.QtWidgets import QTabWidget

        window = self._ventana()
        window.resize(1366, 768)
        tabs = window.findChild(QTabWidget)
        for i in range(tabs.count()):
            if tabs.tabText(i).strip().lower().startswith("inventario"):
                tabs.setCurrentIndex(i)
        window.show()
        QApplication.processEvents()
        caja = window.inventory_overview_label.parentWidget()
        self.assertGreaterEqual(caja.width(), 290)
        # El título de la caja cabe completo en su ancho.
        metrica = caja.fontMetrics()
        self.assertLess(metrica.horizontalAdvance("Selección actual"), caja.width() - 40)
        # Las insignias van en su propia fila: el título tiene todo el ancho.
        self.assertGreaterEqual(window.inventory_overview_label.width(), caja.width() - 60)


if __name__ == "__main__":
    unittest.main()
