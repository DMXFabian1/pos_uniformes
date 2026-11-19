"""«LA PRENDA» en la ficha de Inventario y el «⋯» de arriba (tanda 4 del alta, 2026-11-15).

La escalera se lee de la caja en miniatura (SQLite); la ventana es la de
verdad, con filas falsas, como en las pruebas de las tandas 3 y 5.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QTabWidget
from sqlalchemy import create_engine

from pos_uniformes.database.models import RolUsuario
from pos_uniformes.services import alta_ficha_service as af
from pos_uniformes.ui.dialogs import ficha_prenda_dialogs as fpd
from pos_uniformes.ui.helpers import inventario_pantalla as ip
from pos_uniformes.ui.helpers.inventario_pantalla import LOTE, TALLA
from pos_uniformes.ui.main_window import MainWindow
from tests._ayuda_mini_caja import MiniCaja
from tests.test_inventario_tanda3_pantalla import _cerrar

AHORA = datetime.now(tz=timezone.utc)


def _fila(vid: int, talla: str, producto_id: int) -> dict:
    return {
        "variante_id": vid, "sku": f"SKU{vid:06d}", "producto_id": producto_id,
        "producto_nombre": "Pants Suelto Miguel Hidalgo", "producto_nombre_base": "Pants Suelto Miguel Hidalgo",
        "escuela_nombre": "Miguel Hidalgo", "tipo_prenda_nombre": "Deportivo", "tipo_pieza_nombre": "Pants Suelto",
        "talla": talla, "color": "Sin color", "precio_venta": Decimal("255"), "stock_actual": 3, "stock_bodega": 0,
        "stock_piso": 0, "variante_activa": True, "ultimo_conteo_at": AHORA, "stock_minimo": None,
        "rebaja_tipo": None, "rebaja_precio": None, "rebaja_hasta": None, "categoria_nombre": "Uniformes",
        "marca_nombre": "Propia", "nombre_legacy": "", "origen_legacy": False, "fallback_importacion": False,
        "apartado_cantidad": 0, "costo_referencia": None,
    }


class FichaPrendaPantallaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        caja = MiniCaja(create_engine("sqlite://"))
        cls.pants = caja.productos[("Miguel Hidalgo", "Pants Suelto")]
        cls.ficha_pants = af.leer_ficha(caja.s, cls.pants.id)

    def _ventana(self, rol=RolUsuario.ADMIN, *, otra_prenda: bool = False) -> MainWindow:
        window = MainWindow(user_id=1)
        self.addCleanup(_cerrar, window)
        window.current_role = rol
        self.filas = [_fila(1, "8", self.pants.id), _fila(2, "10", self.pants.id)]
        if otra_prenda:
            otra = _fila(3, "CH", self.pants.id + 1000)
            otra.update(producto_nombre="Bata Jardín", producto_nombre_base="Bata Jardín")
            self.filas.append(otra)
        for fila in self.filas:
            window.inventory_variant_combo.addItem(fila["sku"], fila["variante_id"])
        window.inventory_variant_combo.setCurrentIndex(-1)
        pantalla = window.inventario_pantalla
        self.cargar = Mock(return_value=self.ficha_pants)
        pantalla.cargar_prenda = self.cargar
        pantalla.session_factory = Mock()
        window._load_inventory_snapshot_rows = Mock(return_value=self.filas)
        window._refresh_inventory_overview = Mock()
        window._refresh_inventory_table()
        return window

    def _procesar(self) -> None:
        for _ in range(3):
            QApplication.processEvents()

    def test_la_ficha_ensena_la_escalera_y_la_talla_que_falta(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        pantalla.seleccionar(1)
        seccion = pantalla.ficha.prenda
        self.assertEqual(pantalla.ficha.estado(), TALLA)
        self.assertFalse(seccion.isHidden())
        self.assertEqual(seccion.chips_tallas["8"].property("actual"), "si")
        self.assertEqual(seccion.chips_faltan["EXG"].text(), "EXG ＋ $305")
        # Una sola lectura por prenda y refresco.
        lecturas = self.cargar.call_count
        pantalla.actualizar_ficha()
        pantalla.actualizar_ficha()
        self.assertEqual(self.cargar.call_count, lecturas)
        pantalla.seleccionar(2)
        self.assertEqual(seccion.chips_tallas["10"].property("actual"), "si")

    def test_tocar_la_talla_gris_abre_la_confirmacion_de_esa_talla(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        pantalla.seleccionar(1)
        dialogo = Mock()
        dialogo.return_value.exec.return_value = 0  # Cancelar
        with patch.object(fpd, "TallaNuevaDialog", dialogo):
            pantalla.ficha.prenda.chips_faltan["EXG"].click()
        kw = dialogo.call_args.kwargs
        self.assertEqual((kw["producto_id"], kw["talla"]), (self.pants.id, "EXG"))
        self.assertEqual(kw["session_factory"], pantalla.session_factory)

    def test_otro_color_y_corregir_abren_su_ventana(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        pantalla.seleccionar(1)
        for nombre, boton in (("OtroColorDialog", pantalla.ficha.prenda.boton_color),
                              ("CorregirPrendaDialog", pantalla.ficha.prenda.boton_corregir)):
            dialogo = Mock()
            dialogo.return_value.exec.return_value = 0
            with patch.object(fpd, nombre, dialogo):
                boton.click()
            self.assertEqual(dialogo.call_args.kwargs["producto_id"], self.pants.id, nombre)

    def test_solo_admin_ve_la_prenda(self) -> None:
        window = self._ventana(rol=RolUsuario.CAJERO)
        pantalla = window.inventario_pantalla
        pantalla.seleccionar(1)
        self.assertTrue(pantalla.ficha.prenda.isHidden())
        self.cargar.assert_not_called()
        # Y aunque alguien llame la acción, no abre nada.
        with patch.object(fpd, "TallaNuevaDialog") as dialogo, \
                patch("pos_uniformes.ui.helpers.inventario_ficha_prenda.QMessageBox") as caja:
            pantalla._producto_ficha = self.pants.id
            pantalla.agregar_talla("EXG")
        dialogo.assert_not_called()
        caja.warning.assert_called_once()

    def test_el_menu_de_arriba_lleva_a_la_ficha(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        acciones = {a.text().split("  ")[-1]: a for a in window.inventory_more_button.menu().actions()}
        self.assertIn("Agregar talla o color", acciones)
        self.assertNotIn("Duplicar la talla elegida", acciones)
        with patch.object(ip.QMessageBox, "information") as aviso:
            acciones["Agregar talla o color"].trigger()
        aviso.assert_called_once()
        self.assertIn("LA PRENDA", aviso.call_args.args[2])
        # «Duplicar esta talla» sigue en el «⋯» de la ficha.
        textos = [a.text() for a in pantalla.menu_ficha.actions()]
        self.assertTrue(any("Duplicar esta talla" in t for t in textos))

    def test_cabe_a_1366(self) -> None:
        window = self._ventana()
        window.resize(1366, 768)
        tabs = window.findChild(QTabWidget)
        for i in range(tabs.count()):
            if tabs.tabText(i).strip() == "Inventario":
                tabs.setCurrentIndex(i)
        window.show()
        pantalla = window.inventario_pantalla
        pantalla.seleccionar(1)
        self._procesar()
        seccion = pantalla.ficha.prenda
        self.assertEqual(tabs.currentWidget().horizontalScrollBar().maximum(), 0)
        self.assertEqual(pantalla.ficha.scrolls[TALLA].horizontalScrollBar().maximum(), 0)
        derecha = seccion.width()
        for chip in [*seccion.chips_tallas.values(), *seccion.chips_faltan.values()]:
            self.assertLessEqual(chip.geometry().right(), derecha, chip.text())
            self.assertGreaterEqual(chip.width(), chip.fontMetrics().horizontalAdvance(chip.text()), chip.text())

    # ── Revisión 2026-11-15 ────────────────────────────────────────────────

    def test_un_solo_lapiz_por_nivel(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        pantalla.seleccionar(1)
        arriba = [a.text() for a in window.inventory_more_button.menu().actions() if not a.isSeparator()]
        ficha = [a.text() for a in pantalla.menu_ficha.actions() if not a.isSeparator()]
        botones = [b.text() for b in (pantalla.boton_corregir, pantalla.boton_editar,
                                      pantalla.ficha.prenda.boton_color, pantalla.ficha.prenda.boton_corregir)]
        self.assertEqual([t for t in arriba if "✏️" in t], ["✏️  Corregir la prenda elegida"])
        self.assertEqual([t for t in ficha + botones if "✏️" in t], ["✏️ Corregir prenda"])
        self.assertEqual(pantalla.boton_editar.text(), "🔧  Editar talla")

    def test_corregir_desde_el_menu_de_arriba(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        acciones = {a.text().split("  ")[-1]: a for a in window.inventory_more_button.menu().actions()}
        with patch.object(ip.QMessageBox, "information") as aviso:
            acciones["Corregir la prenda elegida"].trigger()  # sin talla elegida
        aviso.assert_called_once()
        pantalla.seleccionar(1)
        dialogo = Mock()
        dialogo.return_value.exec.return_value = 0
        with patch.object(fpd, "CorregirPrendaDialog", dialogo):
            acciones["Corregir la prenda elegida"].trigger()
        self.assertEqual(dialogo.call_args.kwargs["producto_id"], self.pants.id)

    def test_la_prenda_va_antes_de_los_botones_y_otra_talla_aparte(self) -> None:
        window = self._ventana()
        window.resize(1366, 768)
        tabs = window.findChild(QTabWidget)
        for i in range(tabs.count()):
            if tabs.tabText(i).strip() == "Inventario":
                tabs.setCurrentIndex(i)
        window.show()
        pantalla = window.inventario_pantalla
        pantalla.seleccionar(1)
        self._procesar()
        seccion = pantalla.ficha.prenda
        self.assertLess(seccion.y(), pantalla.boton_corregir.mapTo(seccion.parentWidget(), pantalla.boton_corregir.rect().topLeft()).y())
        # La escalera (con la talla en gris) se ve sin desplazar la ficha.
        area = pantalla.ficha.scrolls[TALLA]
        chip = seccion.chips_faltan["EXG"]
        abajo = chip.mapTo(area.viewport(), chip.rect().bottomLeft()).y()
        self.assertLessEqual(abajo, area.viewport().height(), "la talla en gris queda bajo el pliegue")
        # «＋ Otra talla» no va entre los chips.
        self.assertNotIn(seccion.boton_otra, [seccion.flujo.itemAt(i).widget() for i in range(seccion.flujo.count())])


    # ── «LA PRENDA» con varias tallas de una sola prenda (2026-11-19) ─────

    def test_varias_tallas_de_la_misma_prenda_ensenan_la_prenda(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        pantalla._espejar_a_tabla([1, 2], 1)
        self.assertEqual(sorted(window._selected_inventory_variant_ids()), [1, 2])
        self.assertEqual(pantalla.ficha.estado(), LOTE)
        seccion = pantalla.ficha.prenda_lote
        self.assertFalse(seccion.isHidden())
        self.assertEqual(seccion.chips_tallas["8"].property("actual"), "si")
        self.assertEqual(seccion.chips_tallas["10"].property("actual"), "si")
        # Lo que se toca ahí es de esa prenda.
        dialogo = Mock()
        dialogo.return_value.exec.return_value = 0
        with patch.object(fpd, "TallaNuevaDialog", dialogo):
            seccion.chips_faltan["EXG"].click()
        self.assertEqual(dialogo.call_args.kwargs["producto_id"], self.pants.id)
        # Y el «⋯» de arriba ya no pide elegir una talla.
        acciones = {a.text().split("  ")[-1]: a for a in window.inventory_more_button.menu().actions()}
        corregir = Mock()
        corregir.return_value.exec.return_value = 0
        with patch.object(ip.QMessageBox, "information") as aviso, patch.object(fpd, "CorregirPrendaDialog", corregir):
            acciones["Corregir la prenda elegida"].trigger()
        aviso.assert_not_called()
        self.assertEqual(corregir.call_args.kwargs["producto_id"], self.pants.id)

    def test_la_prenda_entera_elegida_en_por_prenda(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        pantalla.segmento[1].click()
        self._procesar()
        arbol = pantalla.prendas
        modelo_sel = arbol.selectionModel()
        from PyQt6.QtCore import QItemSelectionModel

        modelo_sel.select(arbol.modelo.index(0, 0),
                          QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        self.assertEqual(sorted(window._selected_inventory_variant_ids()), [1, 2])
        self.assertEqual(pantalla.ficha.estado(), LOTE)
        self.assertFalse(pantalla.ficha.prenda_lote.isHidden())

    def test_si_se_mezclan_prendas_se_esconde(self) -> None:
        window = self._ventana(otra_prenda=True)
        pantalla = window.inventario_pantalla
        pantalla._espejar_a_tabla([1, 2], 1)
        self.assertFalse(pantalla.ficha.prenda_lote.isHidden())
        pantalla._espejar_a_tabla([1, 3], 1)
        self.assertEqual(pantalla.ficha.estado(), LOTE)
        self.assertTrue(pantalla.ficha.prenda_lote.isHidden())
        acciones = {a.text().split("  ")[-1]: a for a in window.inventory_more_button.menu().actions()}
        with patch.object(ip.QMessageBox, "information") as aviso:
            acciones["Corregir la prenda elegida"].trigger()
        aviso.assert_called_once()

    def test_el_menu_corrige_y_edita_un_conjunto_aunque_no_ensene_la_prenda(self) -> None:
        # Regresión del 2026-11-19: el «⋯» decía «Elige una talla…» con una talla de conjunto elegida.
        window = self._ventana()
        for fila in self.filas:
            fila["es_conjunto"] = True
        window._refresh_inventory_table()
        pantalla = window.inventario_pantalla
        pantalla.seleccionar(1)
        self.assertTrue(pantalla.ficha.prenda.isHidden())  # sin escalera propia
        acciones = {a.text().split("  ")[-1]: a for a in window.inventory_more_button.menu().actions()}
        with patch.object(ip.QMessageBox, "information") as aviso, \
                patch.object(ip, "editar_datos") as datos, patch.object(ip, "corregir_prenda") as corregir:
            acciones["Más datos de la prenda elegida"].trigger()
            acciones["Corregir la prenda elegida"].trigger()
        aviso.assert_not_called()
        self.assertEqual(datos.call_args.args[2], self.pants.id)
        self.assertEqual(corregir.call_args.args[2], self.pants.id)
        # Con dos tallas del mismo conjunto, igual.
        pantalla._espejar_a_tabla([1, 2], 1)
        self.assertTrue(pantalla.ficha.prenda_lote.isHidden())
        with patch.object(ip.QMessageBox, "information") as aviso, patch.object(ip, "corregir_prenda") as corregir:
            acciones["Corregir la prenda elegida"].trigger()
        aviso.assert_not_called()
        corregir.assert_called_once()

    def test_con_varias_tallas_tampoco_la_ve_quien_no_es_admin(self) -> None:
        window = self._ventana(rol=RolUsuario.CAJERO)
        pantalla = window.inventario_pantalla
        pantalla._espejar_a_tabla([1, 2], 1)
        self.assertEqual(pantalla.ficha.estado(), LOTE)
        self.assertTrue(pantalla.ficha.prenda_lote.isHidden())
        self.cargar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
