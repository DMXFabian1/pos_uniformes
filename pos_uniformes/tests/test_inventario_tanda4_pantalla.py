"""Pestaña Inventario, tanda 4 «Por prenda» (2026-11-13): cambiar de vista,
escalera, desplegar, elegir prenda o talla, ficha, barra de lote, escaneo,
tarjetas, páginas por prenda, 1366 px y rendimiento con ~5,200 tallas."""

from __future__ import annotations

import os
import time
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QItemSelectionModel, QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from pos_uniformes.services.inventario_prenda_service import agrupar_por_prenda, paginar_prendas
from pos_uniformes.ui.helpers.inventario_pantalla import LOTE, POR_PRENDA, POR_TALLA, TALLA, VACIA
from pos_uniformes.ui.helpers.inventario_prendas_vista import COL_TALLAS, VistaPrendas
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


def _fila(vid: int, stock: int, *, talla: str, producto_id: int = 1, producto: str = "Pants 2pz Muestra",
          color: str = "Azul marino", precio: int = 289, dias: int | None = 10) -> dict:
    return {
        "variante_id": vid, "sku": f"SKU{vid:06d}", "producto_id": producto_id, "producto_nombre": producto,
        "producto_nombre_base": producto, "escuela_nombre": "Colegio Muestra", "tipo_prenda_nombre": "Deportivo",
        "tipo_pieza_nombre": "Pants 2pz", "talla": talla, "color": color, "precio_venta": Decimal(precio),
        "stock_actual": stock, "stock_bodega": 0, "stock_piso": 0, "variante_activa": True,
        "ultimo_conteo_at": None if dias is None else AHORA - timedelta(days=dias), "stock_minimo": None,
        "rebaja_tipo": None, "rebaja_precio": None, "rebaja_hasta": None,
        "categoria_nombre": "Uniformes", "marca_nombre": "Propia", "nombre_legacy": "", "origen_legacy": False,
        "fallback_importacion": False, "apartado_cantidad": 0, "costo_referencia": None,
    }


FILAS = [
    _fila(1, 5, talla="10"),
    _fila(2, -2, talla="4"),
    _fila(3, 0, talla="8"),
    _fila(4, 2, talla="6"),
    _fila(5, 6, talla="CH", producto_id=2, producto="Bata Jardín", color="Azul cielo", precio=320),
    _fila(6, 3, talla="GD", producto_id=2, producto="Bata Jardín", color="Azul cielo", precio=335),
    _fila(7, 4, talla="CH", producto_id=2, producto="Bata Jardín", color="Rosa", precio=320),
]


class InventarioTanda4PantallaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self, filas: list[dict] | None = None, *, por_prenda: bool = True, mostrar: bool = False) -> MainWindow:
        window = MainWindow(user_id=1)
        self.addCleanup(_cerrar, window)
        self.filas = [dict(f) for f in (FILAS if filas is None else filas)]
        for fila in self.filas:
            window.inventory_variant_combo.addItem(fila["sku"], fila["variante_id"])
        window.inventory_variant_combo.setCurrentIndex(-1)
        window._load_inventory_snapshot_rows = Mock(return_value=self.filas)
        window._refresh_inventory_overview = Mock()
        window._refresh_inventory_table()
        if mostrar:
            self._mostrar_a_1366(window)
        if por_prenda:
            window.inventario_pantalla.segmento[1].click()
            self._procesar()
        return window

    @staticmethod
    def _procesar() -> None:
        for _ in range(3):
            QApplication.processEvents()

    def _mostrar_a_1366(self, window: MainWindow) -> None:
        window.resize(1366, 768)
        for i in range(window.tabs.count()):
            if window.tabs.tabText(i).strip() == "Inventario":
                window.tabs.setCurrentIndex(i)
        window.show()
        self._procesar()

    @staticmethod
    def _elegir(arbol: VistaPrendas, *indices) -> None:
        modelo_sel = arbol.selectionModel()
        bandera = QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
        for indice in indices:
            modelo_sel.select(indice, bandera)
            bandera = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        modelo_sel.setCurrentIndex(indices[0], QItemSelectionModel.SelectionFlag.NoUpdate)

    # ── Cambiar de vista ────────────────────────────────────────────────

    def test_por_prenda_agrupa_por_prenda_y_color_con_su_escalera(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        self.assertEqual(pantalla.vista, POR_PRENDA)
        self.assertIs(pantalla.pila_lista.currentWidget(), pantalla.prendas)
        self.assertTrue(pantalla.segmento[1].isChecked())
        modelo = pantalla.prendas.modelo
        self.assertEqual(modelo.rowCount(), 3)
        filas = [[modelo.index(r, c).data() for c in range(modelo.columnCount())] for r in range(3)]
        self.assertEqual(filas[0][:4], ["Pants 2pz Muestra · Azul marino", "4·−2  6·2  8·0  10·5", "7", "Tienda"])
        self.assertEqual(filas[1][1:5], ["CH·6  GD·3", "9", "Tienda", "$320–$335"])
        self.assertEqual(filas[2][0], "Bata Jardín · Rosa")
        self.assertEqual(pantalla.subtitulo.text(), "3 prendas · 20 piezas")
        self.assertEqual(pantalla.paginas.text(), "Mostrando 3 prendas")
        self.assertIn("4·−2", modelo.index(0, COL_TALLAS).data(Qt.ItemDataRole.ToolTipRole))
        # La tabla escondida lleva las tallas de la página, prenda tras prenda y en orden de talla.
        self.assertEqual([window._inventory_table_variant_id_at_row(r) for r in range(window.inventory_table.rowCount())],
                         [2, 4, 3, 1, 5, 6, 7])

    def test_volver_a_por_talla_y_la_vista_se_recuerda_al_refrescar(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        window._handle_inventory_filters_changed_reset_page()
        self.assertEqual(pantalla.vista, POR_PRENDA)
        self.assertTrue(pantalla.segmento[1].isChecked())
        pantalla.segmento[0].click()
        self.assertEqual(pantalla.vista, POR_TALLA)
        self.assertIs(pantalla.pila_lista.currentWidget(), window.inventory_table)
        self.assertEqual(pantalla.subtitulo.text(), "7 tallas · 20 piezas")
        self.assertEqual(window.inventory_table.rowCount(), 7)

    # ── Desplegar y elegir ──────────────────────────────────────────────

    def test_tocar_la_flecha_despliega_sin_elegir_y_doble_clic_tambien(self) -> None:
        window = self._ventana(mostrar=True)
        arbol = window.inventario_pantalla.prendas
        prenda = arbol.modelo.index(0, 0)
        rect = arbol.visualRect(prenda)
        QTest.mouseClick(arbol.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(rect.left() + 10, rect.center().y()))
        self.assertTrue(arbol.isExpanded(prenda))
        self.assertEqual(arbol.selectionModel().selectedRows(), [])
        self.assertEqual(arbol.modelo.rowCount(prenda), 4)
        hija = arbol.modelo.index(0, 0, prenda)
        self.assertEqual([arbol.modelo.index(0, c, prenda).data() for c in range(6)][:3], ["SKU000002", "Talla 4", "−2"])
        self.assertEqual(hija.data(Qt.ItemDataRole.UserRole), 2)
        arbol.doubleClicked.emit(prenda)
        self.assertFalse(arbol.isExpanded(prenda))

    def test_elegir_una_talla_hija_alimenta_la_ficha_de_una_talla(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        arbol = pantalla.prendas
        prenda = arbol.modelo.index(0, 0)
        arbol.setExpanded(prenda, True)
        self._elegir(arbol, arbol.modelo.index(3, 0, prenda))  # talla 10
        self.assertEqual(window._selected_inventory_variant_ids(), [1])
        self.assertEqual(window.inventory_variant_combo.currentData(), 1)
        self.assertEqual(pantalla.ficha.estado(), TALLA)
        self.assertEqual(pantalla.ficha.hay.text(), "5")
        self.assertFalse(pantalla.barra_lote.isVisibleTo(pantalla.barra_lote.parentWidget() or pantalla.barra_lote))
        # Doble clic en la talla: lo de siempre (editar).
        window._handle_inventory_table_double_click = Mock()
        arbol.doubleClicked.emit(arbol.modelo.index(3, 0, prenda))
        window._handle_inventory_table_double_click.assert_called_once_with()

    def test_elegir_la_prenda_elige_todas_sus_tallas_y_sale_la_barra_de_lote(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        arbol = pantalla.prendas
        self._elegir(arbol, arbol.modelo.index(0, 0))
        self.assertEqual(sorted(window._selected_inventory_variant_ids()), [1, 2, 3, 4])
        self.assertEqual(pantalla.ficha.estado(), LOTE)
        self.assertEqual(pantalla.ficha.lote_total.text(), "4 tallas · 7 piezas")
        barra = pantalla.barra_lote
        self.assertFalse(barra.isHidden())
        self.assertEqual(barra.texto.text(), "4 tallas · 7 piezas")
        self.assertEqual(barra.etiquetas.text(), "🏷  Imprimir 4 etiquetas")
        # Prenda + una talla de otra prenda: se suman sin repetir.
        otra = arbol.modelo.index(1, 0)
        arbol.setExpanded(otra, True)
        self._elegir(arbol, arbol.modelo.index(0, 0), arbol.modelo.index(0, 0, otra))
        self.assertEqual(sorted(window._selected_inventory_variant_ids()), [1, 2, 3, 4, 5])
        self.assertEqual(barra.texto.text(), "5 tallas · 13 piezas")

    def test_la_barra_de_lote_usa_los_manejadores_de_siempre(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        arbol = pantalla.prendas
        for nombre in ("_handle_inventory_bulk_adjustment", "_handle_inventory_bulk_price_update", "_handle_inventory_print_label"):
            setattr(window, nombre, Mock())
        self._elegir(arbol, arbol.modelo.index(0, 0))
        barra = pantalla.barra_lote
        barra.existencias.click()
        barra.precio.click()
        barra.etiquetas.click()
        window._handle_inventory_bulk_adjustment.assert_called_once_with()
        window._handle_inventory_bulk_price_update.assert_called_once_with()
        window._handle_inventory_print_label.assert_called_once_with()
        barra.quitar.click()
        self.assertEqual(window._selected_inventory_variant_ids(), [])
        self.assertEqual(arbol.selectionModel().selectedRows(), [])
        self.assertTrue(barra.isHidden())
        self.assertEqual(pantalla.ficha.estado(), VACIA)

    def test_etiquetas_de_mas_de_200_tallas_piden_confirmar_desde_la_barra(self) -> None:
        filas = [_fila(i, 1, talla=str(i)) for i in range(1, 206)]
        window = self._ventana(filas)
        pantalla = window.inventario_pantalla
        window._handle_inventory_print_label = Mock()
        self._elegir(pantalla.prendas, pantalla.prendas.modelo.index(0, 0))
        with patch("pos_uniformes.ui.helpers.inventario_pantalla.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.No) as pregunta:
            pantalla.barra_lote.etiquetas.click()
        pregunta.assert_called_once()
        window._handle_inventory_print_label.assert_not_called()

    def test_la_barra_de_lote_tambien_sale_en_por_talla(self) -> None:
        window = self._ventana(por_prenda=False)
        pantalla = window.inventario_pantalla
        tabla = window.inventory_table
        modelo = tabla.selectionModel()
        for fila in (0, 1, 2):
            modelo.select(tabla.model().index(fila, 0),
                          QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.assertFalse(pantalla.barra_lote.isHidden())
        self.assertTrue(pantalla.barra_lote.texto.text().startswith("3 tallas"))
        pantalla.barra_lote.quitar.click()
        self.assertTrue(pantalla.barra_lote.isHidden())

    # ── Escaneo, tarjetas y páginas ─────────────────────────────────────

    def test_escanear_un_codigo_despliega_su_prenda_y_elige_la_talla(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        window.inventory_search_input.setText("SKU000006")
        window._handle_inventory_filters_changed()
        arbol = pantalla.prendas
        elegidas = arbol.selectionModel().selectedRows()
        self.assertEqual([i.data(Qt.ItemDataRole.UserRole) for i in elegidas], [6])
        self.assertTrue(arbol.isExpanded(elegidas[0].parent()))
        self.assertEqual(window._selected_inventory_variant_ids(), [6])
        self.assertEqual(pantalla.ficha.estado(), TALLA)

    def test_para_atender_en_por_prenda_despliega_la_talla(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        pantalla.seleccionar(2)
        arbol = pantalla.prendas
        self.assertEqual([i.data(Qt.ItemDataRole.UserRole) for i in arbol.selectionModel().selectedRows()], [2])
        # Un refresco (p. ej. tras corregir) no pierde lo elegido.
        window._handle_inventory_filters_changed()
        self.assertEqual([i.data(Qt.ItemDataRole.UserRole) for i in arbol.selectionModel().selectedRows()], [2])

    def test_tarjetas_y_filtros_agrupan_solo_lo_que_pasa(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        antes = {llave: t.valor.text() for llave, t in pantalla.tarjetas.items()}
        pantalla.tocar_tarjeta("negativo")
        modelo = pantalla.prendas.modelo
        self.assertEqual(modelo.rowCount(), 1)
        self.assertEqual(modelo.index(0, COL_TALLAS).data(), "4·−2")
        self.assertEqual(pantalla.subtitulo.text(), "1 prenda")
        self.assertEqual({llave: t.valor.text() for llave, t in pantalla.tarjetas.items()}, antes)
        pantalla.tocar_tarjeta("negativo")
        window.inventory_search_input.setText("Rosa")
        window._handle_inventory_filters_changed()
        self.assertEqual([modelo.index(r, 0).data() for r in range(modelo.rowCount())], ["Bata Jardín · Rosa"])

    def test_la_pagina_cuenta_prendas(self) -> None:
        with patch("pos_uniformes.ui.main_window.INVENTORY_PAGE_SIZE", 2):
            window = self._ventana()
            pantalla = window.inventario_pantalla
            self.assertEqual(pantalla.prendas.modelo.rowCount(), 2)
            self.assertEqual(pantalla.paginas.text(), "Mostrando 1–2 de 3 prendas")
            self.assertEqual(window.inventory_table.rowCount(), 6)  # todas las tallas de las 2 prendas
            self.assertFalse(window.inventory_next_page_button.isHidden())
            window._handle_inventory_next_page()
            self.assertEqual(pantalla.paginas.text(), "Mostrando 3–3 de 3 prendas")
            self.assertEqual(pantalla.prendas.modelo.index(0, 0).data(), "Bata Jardín · Rosa")
            # Escanear una talla de otra página salta a esa página.
            pantalla.seleccionar(2)
            self.assertEqual(pantalla.paginas.text(), "Mostrando 1–2 de 3 prendas")

    def test_cambiar_de_pagina_suelta_la_prenda_elegida_y_no_revive(self) -> None:
        with patch("pos_uniformes.ui.main_window.INVENTORY_PAGE_SIZE", 2):
            window = self._ventana()
            pantalla = window.inventario_pantalla
            arbol = pantalla.prendas
            self._elegir(arbol, arbol.modelo.index(0, 0))
            self.assertEqual(sorted(window._selected_inventory_variant_ids()), [1, 2, 3, 4])
            window._handle_inventory_next_page()
            window._handle_inventory_previous_page()
            self.assertEqual(pantalla.paginas.text(), "Mostrando 1–2 de 3 prendas")
            self.assertEqual(window._selected_inventory_variant_ids(), [])
            self.assertEqual(arbol.selectionModel().selectedRows(), [])
            self.assertTrue(pantalla.barra_lote.isHidden())
            self.assertEqual(pantalla.ficha.estado(), VACIA)

    def test_un_refresco_conserva_la_prenda_elegida(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        arbol = pantalla.prendas
        self._elegir(arbol, arbol.modelo.index(0, 0))
        window._handle_inventory_filters_changed()
        self.assertEqual(sorted(window._selected_inventory_variant_ids()), [1, 2, 3, 4])
        self.assertEqual(pantalla.ficha.estado(), LOTE)

    def test_tocar_el_encabezado_ordena_las_prendas(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        modelo = pantalla.prendas.modelo
        pantalla.prendas.header().sectionClicked.emit(2)  # «Hay»
        self.assertEqual([modelo.index(r, 2).data() for r in range(3)], ["4", "7", "9"])
        pantalla.prendas.header().sectionClicked.emit(2)
        self.assertEqual([modelo.index(r, 2).data() for r in range(3)], ["9", "7", "4"])

    # ── 1366 px y rendimiento ───────────────────────────────────────────

    def test_a_1366_nada_cortado_sin_scroll_horizontal(self) -> None:
        largo = "Pants deportivo 2 piezas Instituto Bilingüe Las Américas Secundaria"
        filas = [_fila(i, i % 5 - 1, talla=t, producto=largo)
                 for i, t in enumerate(("4", "6", "8", "10", "12", "14", "16", "CH", "MD", "GD", "EXG"), start=1)]
        window = self._ventana(filas, mostrar=True)
        pantalla = window.inventario_pantalla
        self._elegir(pantalla.prendas, pantalla.prendas.modelo.index(0, 0))
        self._procesar()
        pestana = window.tabs.currentWidget()
        self.assertEqual(pestana.verticalScrollBar().maximum(), 0)
        self.assertEqual(pestana.horizontalScrollBar().maximum(), 0)
        arbol = pantalla.prendas
        self.assertEqual(arbol.horizontalScrollBar().maximum(), 0)
        self.assertLessEqual(arbol.header().length(), arbol.viewport().width())
        self.assertGreaterEqual(arbol.columnWidth(0), 180)
        self.assertGreaterEqual(arbol.columnWidth(COL_TALLAS), 220)
        barra = pantalla.barra_lote
        cortables = [barra.texto, barra.etiquetas, barra.existencias, barra.precio, barra.quitar, *pantalla.segmento]
        for widget in cortables:
            self.assertGreaterEqual(widget.width(), widget.fontMetrics().horizontalAdvance(widget.text()), widget.text())
        self.assertGreaterEqual(arbol.viewport().height(), 4 * 46)

    def test_agrupar_y_pintar_5200_tallas_tarda_menos_de_100_ms(self) -> None:
        tallas = ("4", "6", "8", "10", "12", "14", "16", "CH", "MD", "GD", "EXG", "UNI")
        filas = []
        vid = 0
        for producto in range(700):
            for talla in tallas[: 4 + producto % 9]:
                vid += 1
                filas.append(_fila(vid, (producto + vid) % 9 - 2, talla=talla, producto_id=producto,
                                   producto=f"Prenda {producto}", dias=None if producto % 4 == 0 else producto % 90))
        filas = filas[:5200]
        self.assertEqual(len(filas), 5200)
        arbol = VistaPrendas()
        self.addCleanup(arbol.deleteLater)
        arbol.resize(860, 420)
        arbol.show()
        self._procesar()
        inicio = time.perf_counter()
        grupos = agrupar_por_prenda(filas)
        pagina = paginar_prendas(grupos, 0, 100)
        arbol.modelo.poner(pagina.grupos)
        arbol.setExpanded(arbol.modelo.index(0, 0), True)
        arbol.viewport().grab()  # pinta lo visible, escaleras incluidas
        transcurrido = time.perf_counter() - inicio
        self.assertGreater(len(grupos), 500)
        self.assertLess(transcurrido, 0.1, f"agrupar + pintar tardó {transcurrido * 1000:.0f} ms")


if __name__ == "__main__":
    unittest.main()
