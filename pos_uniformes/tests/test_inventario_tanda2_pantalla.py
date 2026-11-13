"""Pestaña Inventario, tanda 2 «Limpieza» (2026-11-13): lo que se ve y lo que ya no."""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
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
        submenus = {a.text().split("  ")[-1]: a.menu() for a in menu_mas.actions() if a.menu() is not None}
        self.assertIn("Poco usado", submenus)
        qr = [t for t in self._textos_menu(submenus["Poco usado"]) if "QR" in t]
        self.assertEqual(qr, ["Generar QR de la selección", "Generar los QR que faltan", "Regenerar todos los QR"])
        # Fuera de «Poco usado» no queda ninguna acción de QR.
        for titulo, submenu in submenus.items():
            if titulo != "Poco usado":
                self.assertFalse(any("QR" in t for t in self._textos_menu(submenu)), titulo)
        self.assertFalse(any("QR" in t for t in self._textos_menu(menu_mas)))

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

    def test_alta_de_talla_nombra_la_talla_y_la_prenda(self) -> None:
        window = self._ventana()
        window.current_role = RolUsuario.ADMIN
        window._create_or_edit_presentation = Mock(return_value=("SKU000004", 7))
        window.refresh_all = Mock()
        window._set_combo_value = Mock()
        window._load_inventory_snapshot_rows = Mock(
            return_value=[{"variante_id": 7, "talla": "10", "color": "Azul", "producto_nombre_base": "Pants"}]
        )
        with patch.object(QMessageBox, "information") as aviso:
            window._handle_create_variant()
        self.assertEqual(aviso.call_args.args[2], "Talla 10 (Azul) de «Pants» lista.")

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
        # Tanda 3: letra gris en toda la fila y ninguna celda con fondo.
        self.assertEqual(celda.foreground().color().name(), "#9a8f84")
        hay = window.inventory_table.item(0, self._encabezados(window).index("Hay"))
        self.assertEqual(hay.foreground().color().name(), "#9a8f84")
        self.assertEqual(hay.background().style(), Qt.BrushStyle.NoBrush)
        self.assertEqual(celda.background().style(), Qt.BrushStyle.NoBrush)

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

    def test_ficha_toma_la_oferta_de_la_fila_sin_otra_consulta(self) -> None:
        from decimal import Decimal

        from pos_uniformes.services.inventory_overview_service import InventoryOverviewSnapshot

        window = self._ventana()
        window.inventory_filtered_rows = [
            {"variante_id": 8, "rebaja_tipo": "oferta", "rebaja_precio": Decimal("175")},
        ]
        window.inventory_variant_combo.currentData = Mock(return_value=8)
        snapshot = InventoryOverviewSnapshot(
            sku="SKU000008", product_name="Pants", product_active=True, variant_active=True,
            stock_actual=3, apartado_cantidad=0, talla="6", color="Azul marino",
            precio_venta=Decimal("250"), origen_etiqueta="NUEVO", escuela_nombre="General",
            tipo_prenda_nombre="Deportivo", tipo_pieza_nombre="Pants", stock_minimo=None,
            movement_type=None, movement_quantity=None, movement_date="",
        )
        aplicada = Mock()
        window._apply_inventory_overview_view = aplicada
        with patch("pos_uniformes.ui.main_window.get_session"), patch(
            "pos_uniformes.ui.main_window.load_inventory_overview_snapshot", return_value=snapshot
        ):
            window._refresh_inventory_overview()
        self.assertEqual(aplicada.call_args.args[0].stock_hint_label, "Talla 6 · Azul marino · Oferta $175")

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
        window = self._ventana()
        self.assertEqual(
            self._encabezados(window), ["SKU", "Prenda", "Talla", "Color", "Hay", "Dónde", "Precio", "Contada"]
        )
        self.assertEqual(window.inventory_status_badge.text(), "Sin selección")
        menu = window.inventory_more_button.menu()
        menus = [menu] + [a.menu() for a in menu.actions() if a.menu() is not None]
        textos = " ".join(t for m in menus for t in self._textos_menu(m))
        for jerga in ("presentacion", "Presentacion", "fisico", "Categoria", "seleccion", "masivo", "stock"):
            self.assertNotIn(jerga, textos)

    # ── Confirmar antes de desactivar ───────────────────────────────────

    def _fila_elegida(self, *, talla_activa: bool = True, prenda_activa: bool = True) -> dict:
        return {
            "variante_id": 11, "producto_id": 3, "sku": "SKU-11", "producto_nombre": "Pants 2pz Colegio Muestra",
            "talla": "10", "color": "Azul marino", "variante_activo": talla_activa, "producto_activo": prenda_activa,
        }

    def _preparar(self, fila: dict) -> MainWindow:
        window = self._ventana()
        window.current_role = RolUsuario.ADMIN
        window._selected_catalog_row = Mock(return_value=fila)
        window._load_inventory_snapshot_rows = Mock(return_value=[{"producto_id": 3}] * 8)
        window.refresh_all = Mock()
        window._restore_catalog_selection_after_mutation = Mock()
        return window

    def test_desactivar_talla_pregunta_y_cancelar_no_toca_nada(self) -> None:
        window = self._preparar(self._fila_elegida())
        with patch("pos_uniformes.ui.main_window.preguntar_desactivar", return_value=False) as pregunta, patch(
            "pos_uniformes.ui.main_window.toggle_catalog_variant_state"
        ) as cambiar:
            window._handle_toggle_variant()
        cambiar.assert_not_called()
        confirmacion = pregunta.call_args.args[1]
        self.assertIn("¿Desactivar la talla 10 de Pants 2pz Colegio Muestra (Azul marino)?", confirmacion.texto)
        self.assertIn("No se borra, deja de venderse.", confirmacion.texto)

    def test_desactivar_talla_si_confirma_si_desactiva(self) -> None:
        window = self._preparar(self._fila_elegida())
        with patch("pos_uniformes.ui.main_window.preguntar_desactivar", return_value=True), patch(
            "pos_uniformes.ui.main_window.toggle_catalog_variant_state"
        ) as cambiar, patch("pos_uniformes.ui.main_window.get_session"), patch.object(QMessageBox, "information"):
            window._handle_toggle_variant()
        cambiar.assert_called_once()
        self.assertFalse(cambiar.call_args.kwargs["target_state"])

    def test_desactivar_prenda_pregunta_con_sus_tallas(self) -> None:
        window = self._preparar(self._fila_elegida())
        with patch("pos_uniformes.ui.main_window.preguntar_desactivar", return_value=False) as pregunta, patch(
            "pos_uniformes.ui.main_window.toggle_catalog_product_state"
        ) as cambiar:
            window._handle_toggle_product()
        cambiar.assert_not_called()
        self.assertIn("Sus 8 tallas dejan de venderse", pregunta.call_args.args[1].texto)

    def test_activar_no_pregunta(self) -> None:
        window = self._preparar(self._fila_elegida(talla_activa=False))
        with patch("pos_uniformes.ui.main_window.preguntar_desactivar") as pregunta, patch(
            "pos_uniformes.ui.main_window.toggle_catalog_variant_state"
        ) as cambiar, patch("pos_uniformes.ui.main_window.get_session"), patch.object(QMessageBox, "information"):
            window._handle_toggle_variant()
        pregunta.assert_not_called()
        self.assertTrue(cambiar.call_args.kwargs["target_state"])

    def test_botones_con_nombre_entendible(self) -> None:
        window = self._ventana()
        self.assertEqual(window.toggle_variant_button.text(), "Desactivar esta talla…")
        self.assertEqual(window.toggle_product_button.text(), "Desactivar toda la prenda…")

    def test_avisos_al_pasar_el_mouse_en_palabras_de_la_tienda(self) -> None:
        from pos_uniformes.ui.helpers.inventory_help_texts import AYUDAS_INVENTARIO

        window = self._ventana()
        self.assertEqual(
            window.inventory_print_label_button.toolTip(),
            "Con una talla elegida imprime su etiqueta; con varias, las imprime en lote.",
        )
        for nombre, texto in AYUDAS_INVENTARIO.items():
            aviso = getattr(window, nombre).toolTip()
            self.assertEqual(aviso, texto, nombre)
            for jerga in ("presentacion", "presentación", "siguiente fase", "preview", "stock", "mas precision"):
                self.assertNotIn(jerga, aviso.lower(), nombre)

    def test_una_sola_palabra_para_agotada_y_desactivada(self) -> None:
        window = self._ventana()
        opciones_hay = [
            window.inventory_stock_filter_combo.itemText(i) for i in range(window.inventory_stock_filter_combo.count())
        ]
        opciones_estado = [
            window.inventory_status_filter_combo.itemText(i) for i in range(window.inventory_status_filter_combo.count())
        ]
        self.assertIn("Agotadas", opciones_hay)
        self.assertNotIn("En cero", opciones_hay)
        self.assertIn("Desactivadas", opciones_estado)
        self.assertNotIn("Inactivas", opciones_estado)
        self.assertTrue(window.inventory_out_counter.text().startswith("Agotadas"))
        self.assertTrue(window.inventory_inactive_counter.text().startswith("Desactivadas"))


if __name__ == "__main__":
    unittest.main()
