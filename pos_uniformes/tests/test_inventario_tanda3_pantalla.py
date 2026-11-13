"""Pestaña Inventario, tanda 3 «Cara nueva» (2026-11-13): encabezado, «⋯»,
tarjetas que filtran, «Más filtros», ficha en sus tres estados y 1366 px."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QItemSelectionModel
from PyQt6.QtGui import QFocusEvent
from PyQt6.QtWidgets import QApplication, QMessageBox, QTabWidget

from pos_uniformes.ui.helpers.inventario_pantalla import LOTE, TALLA, VACIA
from pos_uniformes.ui.main_window import MainWindow

AHORA = datetime.now(tz=timezone.utc)


def _cerrar(window: MainWindow) -> None:
    from PyQt6 import sip

    if sip.isdeleted(window):
        return
    window._force_close = True
    window.close()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    QApplication.processEvents()


def _fila(vid: int, stock: int, *, talla: str = "8", dias: int | None = 10, producto: str = "Pants 2pz Muestra") -> dict:
    return {
        "variante_id": vid, "sku": f"SKU{vid:06d}", "producto_id": 1, "producto_nombre": producto,
        "producto_nombre_base": producto, "escuela_nombre": "Colegio Muestra", "tipo_prenda_nombre": "Deportivo",
        "tipo_pieza_nombre": "Pants 2pz", "talla": talla, "color": "Azul marino", "precio_venta": Decimal("289"),
        "stock_actual": stock, "stock_bodega": 0, "stock_piso": 0, "variante_activa": True,
        "ultimo_conteo_at": None if dias is None else AHORA - timedelta(days=dias), "stock_minimo": None,
        "rebaja_tipo": None, "rebaja_precio": None, "rebaja_hasta": None,
        "categoria_nombre": "Uniformes", "marca_nombre": "Propia", "nombre_legacy": "", "origen_legacy": False,
        "fallback_importacion": False, "apartado_cantidad": 0, "costo_referencia": None,
    }


FILAS = [
    _fila(1, -2, talla="4"),
    _fila(2, 0, talla="6"),
    _fila(3, 2, talla="8"),
    _fila(4, 12, talla="10", dias=None),
    _fila(5, 7, talla="12", dias=90),
    _fila(6, -1, talla="14"),
]

#: Lo que antes se hacía desde los menús Nuevo/Editar/Existencias/Etiquetas/Más.
ACCIONES_VIEJAS = {
    "_handle_create_category": "Categoría nueva",
    "_handle_create_brand": "Marca nueva",
    "_handle_create_variant": "Agregar talla o color",
    "_handle_duplicate_variant": "Duplicar la talla elegida",
    "_handle_update_product": "Editar la prenda elegida",
    "_handle_product_photo": "Foto del modelo",
    "_handle_update_variant": "Editar la talla elegida",
    "_handle_inventory_bulk_price_update": "Precios en lote",
    "_handle_open_rebajas": "Ofertas y liquidación…",
    "_handle_purchase": "Registrar entrada",
    "_handle_inventory_count": "Conteo físico",
    "_handle_inventory_adjustment": "Corregir existencia",
    "_handle_inventory_bulk_adjustment": "Ajuste en lote",
    "_handle_inventory_print_label": "Imprimir las elegidas",
    "_handle_generate_all_qr": "Generar QR de la selección",
    "_handle_generate_missing_qr": "Generar los QR que faltan",
    "_handle_regenerate_all_qr": "Regenerar todos los QR",
}


class InventarioTanda3PantallaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self, filas: list[dict] | None = None) -> MainWindow:
        window = MainWindow(user_id=1)
        self.addCleanup(_cerrar, window)
        self.filas = [dict(f) for f in (FILAS if filas is None else filas)]
        for fila in self.filas:
            window.inventory_variant_combo.addItem(fila["sku"], fila["variante_id"])
        window.inventory_variant_combo.setCurrentIndex(-1)
        window._load_inventory_snapshot_rows = Mock(return_value=self.filas)
        window._refresh_inventory_overview = Mock()
        window._refresh_inventory_table()
        return window

    @staticmethod
    def _todas_las_acciones(menu) -> dict:
        acciones = {}
        for accion in menu.actions():
            if accion.menu() is not None:
                acciones.update(InventarioTanda3PantallaTests._todas_las_acciones(accion.menu()))
            elif not accion.isSeparator():
                acciones[accion.text().split("  ")[-1]] = accion
        return acciones

    def _visibles(self, window: MainWindow) -> list[int]:
        return [f["variante_id"] for f in window.inventory_filtered_rows]

    # ── A. Encabezado y «⋯» ─────────────────────────────────────────────

    def test_encabezado_un_solo_boton_vino_y_el_menu_de_mas(self) -> None:
        window = self._ventana()
        self.assertEqual(window.inventory_new_button.text(), "＋ Nueva prenda")
        self.assertIsNone(window.inventory_new_button.menu())
        self.assertEqual(window.inventory_more_button.text(), "⋯")
        window._handle_create_product = Mock()
        window.inventory_new_button.click()
        window._handle_create_product.assert_called_once_with()
        self.assertEqual(window.inventario_pantalla.subtitulo.text(), "6 tallas · 21 piezas")

    def test_sin_tarjeta_de_acciones_rapidas(self) -> None:
        from PyQt6.QtWidgets import QGroupBox

        window = self._ventana()
        titulos = {g.title() for g in window.inventory_table.window().findChildren(QGroupBox)}
        self.assertNotIn("Acciones rápidas", titulos)
        for boton in (window.inventory_edit_button, window.inventory_stock_button, window.inventory_labels_button):
            self.assertTrue(boton.isHidden())

    def test_todas_las_acciones_de_antes_siguen_en_el_menu(self) -> None:
        window = self._ventana()
        acciones = self._todas_las_acciones(window.inventory_more_button.menu())
        for manejador, texto in ACCIONES_VIEJAS.items():
            self.assertIn(texto, acciones, texto)
            doble = Mock()
            setattr(window, manejador, doble)
            acciones[texto].trigger()
            doble.assert_called_once_with()

    def test_eliminar_al_final_en_rojo_y_pide_escribir_el_nombre(self) -> None:
        window = self._ventana()
        menu = window.inventory_more_button.menu()
        ultimas = [a for a in menu.actions() if not a.isSeparator()][-2:]
        self.assertEqual([a.text() for a in ultimas], ["🗑  Eliminar la talla elegida…", "🗑  Eliminar toda la prenda…"])
        self.assertIn("#b3261e", ultimas[1].defaultWidget().styleSheet())
        window._handle_delete_product = Mock()
        window.inventario_pantalla.seleccionar(1)
        with patch("pos_uniformes.ui.helpers.inventario_pantalla.QInputDialog.getText", return_value=("Pants", True)), patch.object(
            QMessageBox, "information"
        ):
            ultimas[1].trigger()
        window._handle_delete_product.assert_not_called()
        with patch(
            "pos_uniformes.ui.helpers.inventario_pantalla.QInputDialog.getText",
            return_value=("pants 2PZ muestra", True),
        ):
            ultimas[1].trigger()
        window._handle_delete_product.assert_called_once_with()

    def test_eliminar_con_varias_tallas_elegidas_no_borra_sin_confirmacion_escrita(self) -> None:
        window = self._ventana()
        menu = window.inventory_more_button.menu()
        talla, prenda = [a for a in menu.actions() if not a.isSeparator()][-2:]
        window._handle_delete_variant = Mock()
        window._handle_delete_product = Mock()
        tabla = window.inventory_table
        tabla.selectRow(1)
        tabla.selectionModel().select(
            tabla.model().index(2, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        )
        self.assertEqual(len(window._selected_inventory_variant_ids()), 2)
        with patch("pos_uniformes.ui.helpers.inventario_pantalla.QInputDialog.getText") as escribir, patch.object(
            QMessageBox, "information"
        ) as aviso:
            talla.trigger()
            prenda.trigger()
        escribir.assert_not_called()
        self.assertIn("una sola talla", aviso.call_args.args[2])
        window._handle_delete_variant.assert_not_called()
        window._handle_delete_product.assert_not_called()

    def test_eliminar_sin_talla_elegida_solo_avisa(self) -> None:
        window = self._ventana()
        window._clear_inventory_table_selection()
        window._handle_delete_variant = Mock()
        with patch("pos_uniformes.ui.helpers.inventario_pantalla.QInputDialog.getText") as escribir, patch.object(
            QMessageBox, "information"
        ) as aviso:
            window.inventario_pantalla.eliminar("talla")
        escribir.assert_not_called()
        aviso.assert_called_once()
        window._handle_delete_variant.assert_not_called()

    def test_eliminar_la_talla_pide_su_codigo_de_la_fila_actual(self) -> None:
        window = self._ventana()
        window._handle_delete_variant = Mock()
        window.inventario_pantalla.seleccionar(3)
        with patch(
            "pos_uniformes.ui.helpers.inventario_pantalla.QInputDialog.getText", return_value=("sku000003", True)
        ) as escribir:
            window.inventario_pantalla.eliminar("talla")
        self.assertIn("SKU000003", escribir.call_args.args[2])
        window._handle_delete_variant.assert_called_once_with()

    def test_calendario_y_mercancia_por_nombrar_tambien_en_el_menu(self) -> None:
        window = self._ventana()
        acciones = self._todas_las_acciones(window.inventory_more_button.menu())
        for texto, accion_vieja in (
            ("Calendario de conteos", "conteo_calendario_action"),
            ("Mercancía por nombrar", "por_nombrar_action"),
        ):
            doble = Mock()
            setattr(window, accion_vieja, doble)
            acciones[texto].trigger()
            doble.trigger.assert_called_once_with()

    def test_imprimir_todo_sin_filtro_no_se_deja_y_mas_de_200_pregunta(self) -> None:
        window = self._ventana()
        acciones = self._todas_las_acciones(window.inventory_more_button.menu())
        window._handle_inventory_print_visible_labels = Mock()
        with patch.object(QMessageBox, "information") as aviso:
            acciones["Imprimir todo lo filtrado"].trigger()
        aviso.assert_called_once()
        window._handle_inventory_print_visible_labels.assert_not_called()

        window._handle_inventory_print_label = Mock()
        window._selected_inventory_variant_ids = Mock(return_value=list(range(1, 202)))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as pregunta:
            window.inventario_pantalla.boton_lote_etiquetas.click()
        pregunta.assert_called_once()
        window._handle_inventory_print_label.assert_not_called()

    # ── B. Buscador grande ──────────────────────────────────────────────

    def test_escanear_un_codigo_elige_esa_talla(self) -> None:
        window = self._ventana()
        with patch("pos_uniformes.services.meilisearch_service.is_available", return_value=False):
            window.inventory_search_input.setText("sku000005")
            window._handle_inventory_filters_changed()
        self.assertEqual(window.inventory_variant_combo.currentData(), 5)
        self.assertEqual(window.inventario_pantalla.ficha.estado(), TALLA)

    def test_aviso_de_busqueda_cortada_debajo_del_buscador(self) -> None:
        window = self._ventana()
        window.inventory_results_label.setText("500 de 5,153 tallas · 900 piezas · ⚠ Mostrando los primeros 500; afina la búsqueda")
        window.inventario_pantalla.al_refrescar()
        self.assertEqual(window.inventario_pantalla.subtitulo.text(), "500 de 5,153 tallas · 900 piezas")
        self.assertIn("afina la búsqueda", window.inventario_pantalla.aviso_busqueda.text())
        self.assertFalse(window.inventario_pantalla.aviso_busqueda.isHidden())

    # ── C. Tarjetas que filtran ─────────────────────────────────────────

    def test_tarjetas_cuentan_y_filtran_y_se_apagan_al_tocarlas_otra_vez(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        numeros = {llave: t.valor.text() for llave, t in pantalla.tarjetas.items()}
        self.assertEqual(numeros, {"negativo": "2", "se_acabo": "1", "pocas": "1", "sin_contar": "2"})
        self.assertTrue(window.inventory_clear_filters_button.isHidden())

        self.assertEqual(pantalla.tarjetas["negativo"].nota.text(), "Se vendió más de lo que había")
        pantalla.tarjetas["negativo"].tocada.emit("negativo")
        self.assertEqual(self._visibles(window), [1, 6])
        self.assertEqual(pantalla.subtitulo.text(), "2 de 6 tallas")
        self.assertTrue(pantalla.tarjetas["negativo"].esta_prendida())
        self.assertFalse(window.inventory_clear_filters_button.isHidden())
        # Las demás tarjetas siguen contando sobre todo lo filtrado, no solo lo de la tocada.
        self.assertEqual(pantalla.tarjetas["sin_contar"].valor.text(), "2")

        pantalla.tarjetas["negativo"].tocada.emit("negativo")
        self.assertEqual(len(self._visibles(window)), 6)
        self.assertFalse(pantalla.tarjetas["negativo"].esta_prendida())

    def test_quitar_filtros_tambien_apaga_la_tarjeta(self) -> None:
        window = self._ventana()
        window.inventario_pantalla.tocar_tarjeta("sin_contar")
        self.assertEqual(self._visibles(window), [4, 5])
        window.inventory_clear_filters_button.click()
        self.assertIsNone(window.inventario_pantalla.tarjeta)
        self.assertEqual(len(self._visibles(window)), 6)

    def test_sin_chips_viejos_a_la_vista(self) -> None:
        window = self._ventana()
        for chip in (window.inventory_negative_counter, window.inventory_out_counter, window.inventory_inactive_counter):
            self.assertTrue(chip.isHidden())
        # «Desactivadas» vive ahora en «Más filtros» → Estado.
        self.assertIs(window.inventory_status_filter_combo.parentWidget(), window.inventario_pantalla.mas_filtros_panel)

    # ── D. Filtros ──────────────────────────────────────────────────────

    def test_cuatro_filtros_a_la_vista_y_lo_demas_en_mas_filtros(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        self.assertTrue(pantalla.mas_filtros_panel.isHidden())
        self.assertEqual(window.inventory_piece_filter_combo.text(), "Prenda: todas")
        for filtro in (
            window.inventory_school_filter_combo,
            window.inventory_piece_filter_combo,
            window.inventory_size_filter_combo,
            window.inventory_color_filter_combo,
        ):
            self.assertIsNot(filtro.parentWidget(), pantalla.mas_filtros_panel)
        for filtro in (
            window.inventory_brand_filter_combo,
            window.inventory_type_filter_combo,
            window.inventory_use_filter_combo,
            window.inventory_stock_filter_combo,
            window.inventory_precio_filter_combo,
            window.inventory_conteo_filter_combo,
            window.inventory_precio_text_input,
        ):
            self.assertIs(filtro.parentWidget(), pantalla.mas_filtros_panel)
        pantalla.mas_filtros.setChecked(True)
        self.assertFalse(pantalla.mas_filtros_panel.isHidden())

        window.inventory_stock_filter_combo.setCurrentIndex(window.inventory_stock_filter_combo.findData("zero"))
        self.assertEqual(pantalla.mas_filtros.text(), "Más filtros (1)")
        self.assertFalse(window.inventory_clear_filters_button.isHidden())
        self.assertEqual(self._visibles(window), [2])
        fichas = [b.text() for b in window.inventory_active_filters_wrap.findChildren(type(window.inventory_clear_filters_button))]
        self.assertIn("Hay: Agotadas  ×", fichas)

    def test_combos_de_mas_filtros_no_pierden_su_rotulo(self) -> None:
        from pos_uniformes.ui.helpers.inventario_combo_rotulo import texto_visible

        window = self._ventana()
        self._mostrar_a_1366(window)
        pantalla = window.inventario_pantalla
        pantalla.mas_filtros.setChecked(True)
        combo = window.inventory_stock_filter_combo
        self.assertEqual(texto_visible(combo), "Hay: todas")
        combo.setCurrentIndex(combo.findData("negative"))
        QApplication.processEvents()
        self.assertEqual(texto_visible(combo), "Hay: En negativo")
        # Cabe la opción más larga ya con su rótulo, y se pinta sin errores.
        largo = combo.fontMetrics().horizontalAdvance("Hay: Bajo el mínimo")
        self.assertGreater(combo.width(), largo)
        self.assertFalse(combo.grab().isNull())
        # La ficha de abajo no repite el rótulo.
        fichas = [b.text() for b in window.inventory_active_filters_wrap.findChildren(type(window.inventory_clear_filters_button))]
        self.assertIn("Hay: En negativo  ×", fichas)
        alturas = {w.height() for w in (combo, window.inventory_use_filter_combo, window.inventory_brand_filter_combo)}
        self.assertEqual(len(alturas), 1, alturas)  # misma altura los dos tipos de control

    def test_segmento_empieza_en_por_talla_y_por_prenda_ya_se_puede_usar(self) -> None:
        # Tanda 4: «Por prenda» dejó de estar apagada (sus pruebas, en test_inventario_tanda4_pantalla).
        window = self._ventana()
        por_talla, por_prenda = window.inventario_pantalla.segmento
        self.assertTrue(por_talla.isChecked())
        self.assertTrue(por_prenda.isEnabled())
        self.assertIn("escalera de tallas", por_prenda.toolTip())
        # Tocar «Por talla» otra vez no la apaga: siempre queda una vista marcada.
        por_talla.click()
        self.assertTrue(por_talla.isChecked())
        self.assertTrue(window.inventario_pantalla.segmento_grupo.exclusive())

    # ── E. Tabla ────────────────────────────────────────────────────────

    def test_tocar_el_encabezado_ordena_todas_las_filas(self) -> None:
        window = self._ventana()
        columna = [window.inventory_table.horizontalHeaderItem(i).text() for i in range(8)].index("Hay")
        window.inventario_pantalla.tocar_encabezado(columna)
        self.assertEqual(self._visibles(window), [1, 6, 2, 3, 5, 4])
        window.inventario_pantalla.tocar_encabezado(columna)
        self.assertEqual(self._visibles(window), [4, 5, 3, 2, 6, 1])
        window.inventario_pantalla.tocar_encabezado(columna)
        self.assertEqual(self._visibles(window), [1, 2, 3, 4, 5, 6])

    def test_fila_elegida_conserva_el_rojo_del_negativo(self) -> None:
        window = self._ventana()
        self._mostrar_a_1366(window)
        tabla = window.inventory_table
        columna = [tabla.horizontalHeaderItem(i).text() for i in range(tabla.columnCount())].index("Hay")
        tabla.selectRow(0)  # la talla 4, con −2
        tabla.selectionModel().select(
            tabla.model().index(5, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        )
        QApplication.processEvents()
        self.assertEqual(tabla.item(0, columna).text(), "−2")
        imagen = tabla.viewport().grab(tabla.visualItemRect(tabla.item(0, columna))).toImage()
        rojos = sum(
            1
            for x in range(imagen.width())
            for y in range(imagen.height())
            if (c := imagen.pixelColor(x, y)).red() > 140 and c.green() < 90 and c.blue() < 90
        )
        self.assertGreater(rojos, 5)

    def test_paginacion_discreta(self) -> None:
        window = self._ventana()
        self.assertEqual(window.inventario_pantalla.paginas.text(), "Mostrando 6 tallas")
        self.assertEqual(window.inventory_previous_page_button.text(), "◀")
        self.assertTrue(window.inventory_pagination_label.isHidden())
        # Una sola página: sin flechas apagadas de adorno.
        self.assertTrue(window.inventory_previous_page_button.isHidden())
        self.assertTrue(window.inventory_next_page_button.isHidden())

    def test_con_varias_paginas_salen_las_flechas(self) -> None:
        window = self._ventana([_fila(i, 3, talla=str(i)) for i in range(1, 121)])
        self.assertFalse(window.inventory_previous_page_button.isHidden())
        self.assertFalse(window.inventory_next_page_button.isHidden())
        self.assertIn("de 120", window.inventario_pantalla.paginas.text())

    def test_el_buscador_marca_el_foco(self) -> None:
        window = self._ventana()
        marco = window.inventario_pantalla.foco_buscador.marco
        entrada = window.inventory_search_input
        self.assertEqual(marco.property("foco"), "no")
        QApplication.sendEvent(entrada, QFocusEvent(QEvent.Type.FocusIn))
        self.assertEqual(marco.property("foco"), "si")
        QApplication.sendEvent(entrada, QFocusEvent(QEvent.Type.FocusOut))
        self.assertEqual(marco.property("foco"), "no")

    # ── F. Ficha en sus tres estados ────────────────────────────────────

    def test_ficha_vacia_con_para_atender(self) -> None:
        window = self._ventana()
        ficha = window.inventario_pantalla.ficha
        self.assertEqual(ficha.estado(), VACIA)
        self.assertIn("Elige una talla", ficha.vacio.text())
        self.assertEqual([b.variante_id for b in ficha.atender_botones], [1, 6, 2])
        ficha.atender_botones[1].tocada.emit(6)
        self.assertEqual(window.inventory_variant_combo.currentData(), 6)
        self.assertEqual(ficha.estado(), TALLA)

    def test_para_atender_con_nombre_largo_no_pierde_talla_ni_color(self) -> None:
        largo = "Pants deportivo 2 piezas Instituto Bilingüe Las Américas Secundaria"
        window = self._ventana([_fila(1, -2, talla="10", producto=largo), _fila(2, 0, talla="CH", producto=largo)])
        self._mostrar_a_1366(window)
        filas = window.inventario_pantalla.ficha.atender_botones
        self.assertEqual(len(filas), 2)
        for fila, talla in zip(filas, ("Talla 10", "Talla CH")):
            self.assertEqual(fila.titulo.completo(), largo)
            self.assertIn(largo, fila.titulo.toolTip())
            self.assertTrue(fila.titulo.text().endswith("…"), fila.titulo.text())
            self.assertLessEqual(fila.titulo.fontMetrics().horizontalAdvance(fila.titulo.text()), fila.titulo.width())
            self.assertTrue(fila.talla.text().startswith(f"{talla} · Azul marino"))
            self.assertGreaterEqual(fila.talla.width(), fila.talla.fontMetrics().horizontalAdvance(fila.talla.text()))
        self.assertEqual(filas[0].motivo.text(), "En negativo (−2)")

    def test_ficha_de_una_talla(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        window.inventory_variant_combo.setCurrentIndex(window.inventory_variant_combo.findData(1))
        vista = Mock(overview_label="SKU000001", last_movement_label="Último movimiento: Venta −1 · 12/11/2026")
        pantalla.al_cambiar_ficha(vista)
        ficha = pantalla.ficha
        self.assertEqual(ficha.estado(), TALLA)
        self.assertEqual(ficha.nombre.text(), "Pants 2pz Muestra")
        self.assertEqual(ficha.sub.text(), "Talla 4 · Azul marino · SKU000001")
        self.assertEqual(ficha.hay.text(), "−2")
        self.assertEqual(ficha.precio.text(), "$289")
        self.assertEqual(ficha.chip_estado.text(), "En negativo")
        self.assertEqual(ficha.contada.text(), "Hace 10 días")
        self.assertEqual(ficha.movimiento.text(), "Venta −1 · 12/11/2026")
        textos = [pantalla.boton_corregir.text(), window.inventory_print_label_button.text(),
                  pantalla.boton_editar.text(), pantalla.boton_movimientos.text()]
        self.assertEqual(textos, ["🧮  Corregir existencia", "🏷  Imprimir etiqueta", "✏️  Editar", "📜  Ver movimientos"])
        # Desactivar va en el «⋯» de la ficha, con el texto (y la confirmación) de siempre.
        pantalla.menu_ficha.aboutToShow.emit()
        self.assertEqual(pantalla.accion_talla.text(), "Desactivar esta talla…")
        window._handle_toggle_variant = Mock()
        pantalla.accion_talla.trigger()
        window._handle_toggle_variant.assert_called_once_with()

    def test_ver_movimientos_abre_el_historial_filtrado(self) -> None:
        window = self._ventana()
        window.inventory_variant_combo.setCurrentIndex(window.inventory_variant_combo.findData(3))
        window._handle_history_filter = Mock()
        window.inventario_pantalla.boton_movimientos.click()
        self.assertEqual(window.history_sku_input.text(), "SKU000003")
        window._handle_history_filter.assert_called_once_with()
        self.assertEqual(window.tabs.tabText(window.tabs.currentIndex()), "Historial inventarios")

    def test_ver_movimientos_limpia_los_otros_filtros_del_historial(self) -> None:
        from datetime import date

        window = self._ventana()
        window._handle_history_filter = Mock()
        hoy = date.today()
        window.history_from_input.blockSignals(True)
        window.history_from_input.setDate(hoy)
        window.history_from_input.blockSignals(False)
        window.history_type_combo.blockSignals(True)
        window.history_type_combo.setCurrentIndex(window.history_type_combo.count() - 1)
        window.history_type_combo.blockSignals(False)
        window.inventory_variant_combo.setCurrentIndex(window.inventory_variant_combo.findData(3))
        window.inventario_pantalla.boton_movimientos.click()
        self.assertEqual(window.history_sku_input.text(), "SKU000003")
        self.assertEqual(window.history_type_combo.currentIndex(), 0)
        self.assertEqual(window.history_from_input.date(), window.history_from_input.minimumDate())
        window._handle_history_filter.assert_called_once_with()

    def test_escanear_con_tarjeta_prendida_apaga_la_tarjeta_y_elige_la_talla(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        pantalla.tocar_tarjeta("negativo")
        self.assertEqual(self._visibles(window), [1, 6])
        with patch("pos_uniformes.services.meilisearch_service.is_available", return_value=False):
            window.inventory_search_input.setText("SKU000004")
            window._handle_inventory_filters_changed()
        self.assertIsNone(pantalla.tarjeta)
        self.assertEqual(window.inventory_variant_combo.currentData(), 4)
        self.assertEqual(pantalla.ficha.estado(), TALLA)

    def test_ficha_de_varias_tallas(self) -> None:
        window = self._ventana()
        tabla = window.inventory_table
        modelo = tabla.selectionModel()
        for fila in (2, 3, 4):
            modelo.select(
                tabla.model().index(fila, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )
        pantalla = window.inventario_pantalla
        self.assertEqual(pantalla.ficha.estado(), LOTE)
        self.assertEqual(pantalla.ficha.lote_total.text(), "3 tallas · 21 piezas")
        self.assertEqual(pantalla.boton_lote_etiquetas.text(), "🏷  Imprimir 3 etiquetas")
        window._handle_inventory_bulk_price_update = Mock()
        pantalla.boton_lote_precio.click()
        window._handle_inventory_bulk_price_update.assert_called_once_with()

    # ── Nada cortado a 1366 × 768, un solo scroll ───────────────────────

    def test_a_1366_nada_cortado_y_un_solo_scroll(self) -> None:
        window = self._ventana()
        window.resize(1366, 768)
        tabs = window.findChild(QTabWidget)
        for i in range(tabs.count()):
            if tabs.tabText(i).strip() == "Inventario":
                tabs.setCurrentIndex(i)
        window.show()
        window.inventario_pantalla.seleccionar(1)
        for _ in range(3):
            QApplication.processEvents()
        pestana = tabs.currentWidget()
        self.assertEqual(pestana.verticalScrollBar().maximum(), 0)
        self.assertEqual(pestana.horizontalScrollBar().maximum(), 0)
        pantalla = window.inventario_pantalla
        self.assertGreaterEqual(pantalla.ficha.width(), 400)
        self.assertLessEqual(pantalla.ficha.width(), 440)
        cortables = [window.inventory_new_button, pantalla.mas_filtros, pantalla.boton_corregir,
                     window.inventory_print_label_button, pantalla.boton_movimientos]
        for tarjeta in pantalla.tarjetas.values():
            cortables += [tarjeta.titulo, tarjeta.nota]
        for widget in cortables:
            self.assertGreaterEqual(widget.width(), widget.fontMetrics().horizontalAdvance(widget.text()), widget.text())
        # La lista enseña varias filas sin desplazar la página.
        self.assertGreaterEqual(window.inventory_table.viewport().height(), 6 * 36)

    def _mostrar_a_1366(self, window: MainWindow) -> None:
        window.resize(1366, 768)
        for i in range(window.tabs.count()):
            if window.tabs.tabText(i).strip() == "Inventario":
                window.tabs.setCurrentIndex(i)
        window.show()
        for _ in range(3):
            QApplication.processEvents()

    def test_a_1366_las_cifras_de_la_ficha_no_se_aplastan_con_chips_y_nombre_largo(self) -> None:
        largo = "Pants deportivo 2 piezas Instituto Bilingüe Las Américas Secundaria"
        filas = [_fila(1, 0, talla="CH", producto=largo), _fila(2, -3, talla="10", producto=largo), _fila(3, 5)]
        filas[0]["variante_activa"] = False
        window = self._ventana(filas)
        self._mostrar_a_1366(window)
        pantalla = window.inventario_pantalla
        ficha = pantalla.ficha
        for vid in (1, 2):
            pantalla.seleccionar(vid)
            for _ in range(3):
                QApplication.processEvents()
            self.assertEqual(ficha.estado(), TALLA)
            self.assertFalse(ficha.chip_estado.isHidden())
            for cifra in (ficha.hay, ficha.precio):
                self.assertGreaterEqual(cifra.height(), cifra.sizeHint().height(), cifra.text())
            self.assertGreaterEqual(ficha.total.height(), ficha.total.sizeHint().height())
        self.assertTrue(ficha.chip_apagada.isHidden())
        pantalla.seleccionar(1)
        self.assertFalse(ficha.chip_apagada.isHidden())


if __name__ == "__main__":
    unittest.main()
