"""Pestaña Inventario, tanda 5 (2026-11-13): «Se va a acabar» con el ritmo de
la Libreta, «La pidieron y no había», aviso de precio que baja y «Conteos por
jornada» en el menú «⋯»."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication, QTabWidget

from pos_uniformes.database.models import RolUsuario
from pos_uniformes.services.inventario_ritmo_service import CacheVentas
from pos_uniformes.services.inventario_tarjetas_service import SE_VA_A_ACABAR
from pos_uniformes.ui.helpers.inventario_pantalla import TALLA, VACIA
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


def _fila(vid: int, stock: int, *, talla: str = "8", dias: int | None = 10, producto: str = "Pants 2pz Muestra",
          precio: str = "289") -> dict:
    return {
        "variante_id": vid, "sku": f"SKU{vid:06d}", "producto_id": 1, "producto_nombre": producto,
        "producto_nombre_base": producto, "escuela_nombre": "Colegio Muestra", "tipo_prenda_nombre": "Deportivo",
        "tipo_pieza_nombre": "Pants 2pz", "talla": talla, "color": "Azul marino", "precio_venta": Decimal(precio),
        "stock_actual": stock, "stock_bodega": 0, "stock_piso": 0, "variante_activa": True,
        "ultimo_conteo_at": None if dias is None else AHORA - timedelta(days=dias), "stock_minimo": None,
        "rebaja_tipo": None, "rebaja_precio": None, "rebaja_hasta": None,
        "categoria_nombre": "Uniformes", "marca_nombre": "Propia", "nombre_legacy": "", "origen_legacy": False,
        "fallback_importacion": False, "apartado_cantidad": 0, "costo_referencia": None,
    }


FILAS = [
    _fila(1, -2, talla="4"),
    _fila(2, 0, talla="6"),           # se acabó y la piden
    _fila(3, 2, talla="8"),           # se va a acabar (12 en 30 días → 5 días)
    _fila(4, 12, talla="10", dias=None),
    _fila(5, 7, talla="12", dias=90),
    _fila(6, 0, talla="14", dias=3),  # cero contado, nadie la pide
]
VENTAS = {"SKU000002": 6, "SKU000003": 12, "SKU000004": 3}
PEDIDAS = {"SKU000002": 4}


class InventarioTanda5PantallaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self, *, rol=RolUsuario.ADMIN, ventas=VENTAS, pedidas=PEDIDAS, filas=None) -> MainWindow:
        window = MainWindow(user_id=1)
        self.addCleanup(_cerrar, window)
        window.current_role = rol
        self.filas = [dict(f) for f in (FILAS if filas is None else filas)]
        for fila in self.filas:
            window.inventory_variant_combo.addItem(fila["sku"], fila["variante_id"])
        window.inventory_variant_combo.setCurrentIndex(-1)
        pantalla = window.inventario_pantalla
        self.cargar_ventas = Mock(side_effect=ventas) if isinstance(ventas, Exception) else Mock(return_value=ventas)
        self.cargar_pedidas = Mock(side_effect=pedidas) if isinstance(pedidas, Exception) else Mock(return_value=pedidas)
        # Cachés nuevas: lo que la ventana leyó al abrir (base de pruebas) no cuenta.
        pantalla.cache_ventas = CacheVentas(self.cargar_ventas)
        pantalla.cache_demanda = CacheVentas(self.cargar_pedidas)
        window._load_inventory_snapshot_rows = Mock(return_value=self.filas)
        window._refresh_inventory_overview = Mock()
        window._refresh_inventory_table()
        return window

    def _mostrar_a_1366(self, window: MainWindow) -> QTabWidget:
        window.resize(1366, 768)
        tabs = window.findChild(QTabWidget)
        for i in range(tabs.count()):
            if tabs.tabText(i).strip() == "Inventario":
                tabs.setCurrentIndex(i)
        window.show()
        for _ in range(3):
            QApplication.processEvents()
        return tabs

    # ── A. «Se va a acabar» ──────────────────────────────────────────────

    def test_para_atender_sube_la_agotada_que_piden_y_la_que_se_va_a_acabar(self) -> None:
        window = self._ventana()
        ficha = window.inventario_pantalla.ficha
        self.assertEqual(ficha.estado(), VACIA)
        self.assertEqual(ficha.atender_ids[:3], [1, 2, 3])
        motivos = [f.motivo.text() for f in ficha.atender_botones]
        self.assertEqual(motivos[1], "Se acabó · la pidieron 4 veces")
        self.assertEqual(motivos[2], "Se va a acabar · alcanza para 5 días")
        self.assertEqual(ficha.atender_botones[2].motivo.property("tono"), "warning")

    def test_se_va_a_acabar_cuenta_filtra_y_se_quita(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        ficha = pantalla.ficha
        self.assertFalse(ficha.acabarse.isHidden())
        self.assertEqual(ficha.acabarse_titulo.text(), "⏳  2 tallas se van a acabar")
        self.assertTrue(pantalla.chip_acabarse.isHidden())
        ficha.acabarse_boton.click()
        self.assertEqual(pantalla.tarjeta, SE_VA_A_ACABAR)
        self.assertEqual([f["variante_id"] for f in window.inventory_filtered_rows], [2, 3])
        self.assertFalse(pantalla.chip_acabarse.isHidden())
        self.assertFalse(window.inventory_clear_filters_button.isHidden())
        self.assertEqual(ficha.acabarse_boton.text(), "Ver todas")
        pantalla.chip_acabarse.click()
        self.assertIsNone(pantalla.tarjeta)
        self.assertEqual(len(window.inventory_filtered_rows), 6)
        self.assertTrue(pantalla.chip_acabarse.isHidden())

    def test_la_libreta_se_lee_una_vez_por_unos_minutos(self) -> None:
        window = self._ventana()
        for _ in range(3):
            window._handle_inventory_filters_changed()
        self.assertEqual(self.cargar_ventas.call_count, 1)
        self.assertEqual(self.cargar_pedidas.call_count, 1)

    def test_si_la_libreta_falla_la_pantalla_sigue_sin_ese_dato(self) -> None:
        window = self._ventana(ventas=RuntimeError("sin base"), pedidas=RuntimeError("sin tabla"))
        pantalla = window.inventario_pantalla
        self.assertEqual(len(window.inventory_filtered_rows), 6)
        self.assertTrue(pantalla.ficha.acabarse.isHidden())
        pantalla.seleccionar(3)
        self.assertEqual(pantalla.ficha.estado(), TALLA)
        self.assertTrue(pantalla.ficha.venta.isHidden())
        self.assertTrue(pantalla.ficha.pedidas.isHidden())

    # ── B. Ficha con ritmo y «La pidieron…» ──────────────────────────────

    def test_ficha_con_ritmo_y_la_pidieron(self) -> None:
        window = self._ventana()
        pantalla = window.inventario_pantalla
        ficha = pantalla.ficha
        pantalla.seleccionar(2)
        self.assertEqual(ficha.venta.text(), "Se vende ~1 por semana · ya no hay")
        self.assertEqual(ficha.venta.property("tono"), "danger")
        self.assertEqual(ficha.pedidas.text(), "La pidieron 4 veces en 30 días y no había")
        self.assertFalse(ficha.pedidas.isHidden())
        pantalla.seleccionar(3)
        self.assertEqual(ficha.venta.text(), "Se vende ~3 por semana · alcanza para 5 días")
        self.assertEqual(ficha.chip_estado.text(), "Quedan pocas")
        self.assertTrue(ficha.pedidas.isHidden())
        pantalla.seleccionar(5)
        self.assertEqual(ficha.venta.text(), "Sin ventas en 30 días")

    def test_se_va_a_acabar_sale_en_el_estado_si_no_hay_otro(self) -> None:
        window = self._ventana(ventas={"SKU000004": 30})  # 12 piezas, 1 al día → 12 días
        pantalla = window.inventario_pantalla
        pantalla.seleccionar(4)
        self.assertEqual(pantalla.ficha.chip_estado.text(), "Se va a acabar")
        self.assertEqual(pantalla.ficha.chip_estado.property("tono"), "warning")

    def test_la_demanda_solo_la_ve_el_admin(self) -> None:
        window = self._ventana(rol=RolUsuario.CAJERO)
        pantalla = window.inventario_pantalla
        self.assertEqual(self.cargar_pedidas.call_count, 0)
        motivos = [f.motivo.text() for f in pantalla.ficha.atender_botones]
        self.assertNotIn("Se acabó · la pidieron 4 veces", motivos)
        pantalla.seleccionar(2)
        self.assertTrue(pantalla.ficha.pedidas.isHidden())
        self.assertFalse(pantalla.ficha.venta.isHidden())

    # ── E. main_window solo conecta ──────────────────────────────────────

    def test_los_manejadores_movidos_delegan_en_inventario_acciones(self) -> None:
        from unittest.mock import patch

        window = self._ventana()
        movidos = {
            "_handle_inventory_adjustment": "corregir_existencia",
            "_handle_inventory_bulk_adjustment": "corregir_existencias_en_lote",
            "_handle_inventory_bulk_price_update": "cambiar_precios_en_lote",
            "_handle_inventory_count": "conteo_fisico_viejo",
        }
        for metodo, funcion in movidos.items():
            with patch(f"pos_uniformes.ui.helpers.inventario_acciones.{funcion}") as doble:
                getattr(window, metodo)()
            doble.assert_called_once_with(window)

    def test_sin_permiso_no_se_abre_nada(self) -> None:
        from unittest.mock import patch

        window = self._ventana(rol=RolUsuario.CAJERO)
        window._prompt_inventory_bulk_price_data = Mock()
        with patch("pos_uniformes.ui.helpers.inventario_acciones.QMessageBox.warning") as aviso:
            window._handle_inventory_bulk_price_update()
        aviso.assert_called_once()
        window._prompt_inventory_bulk_price_data.assert_not_called()

    # ── C. Aviso de precio que baja ──────────────────────────────────────

    def _precios(self, nuevos: dict[int, str]):
        """Ventana ADMIN con el diálogo de «Precios en lote» ya contestado y la base de mentiras."""
        from unittest.mock import patch

        window = self._ventana()
        window._prompt_inventory_bulk_price_data = Mock(return_value={
            "tipo_fuente": "SELECCION", "tipo_operacion": "FIJO", "referencia": "LOTE-1", "motivo": "", "observacion": "",
            "items": [{"variante_id": vid, "precio_nuevo": precio, "estado": "OK"} for vid, precio in nuevos.items()],
        })
        window.refresh_all = Mock()
        aplicar = Mock(return_value={"total_filas": len(nuevos), "aplicadas": 1, "suben": 0, "bajan": 1, "sin_cambios": 0})
        parches = [
            patch("pos_uniformes.ui.helpers.inventario_acciones.get_session"),
            patch("pos_uniformes.ui.helpers.inventario_acciones.CatalogService.aplicar_cambio_masivo_precio", aplicar),
            patch("pos_uniformes.ui.helpers.inventario_acciones.QMessageBox.information"),
        ]
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        return window, aplicar

    def test_aviso_rojo_con_cancelar_por_defecto_y_cancelar_no_cambia_nada(self) -> None:
        from unittest.mock import patch

        from PyQt6.QtWidgets import QMessageBox

        window, aplicar = self._precios({3: "250", 4: "300"})
        vistas = []
        with patch.object(QMessageBox, "exec", new=lambda caja: vistas.append(caja) or 0):
            window._handle_inventory_bulk_price_update()
        self.assertEqual(len(vistas), 1)
        caja = vistas[0]
        self.assertEqual(caja.defaultButton().text(), "Cancelar")
        self.assertIs(caja.escapeButton(), caja.defaultButton())
        self.assertIn("1 precio baja", caja.text())
        self.assertIn("SKU000003 · talla 8: baja de $289 a $250", caja.text())
        self.assertNotIn("SKU000004", caja.text())  # sube: no se avisa
        self.assertIn("#b3261e", caja.text())
        aplicar.assert_not_called()
        window.refresh_all.assert_not_called()

    def test_confirmar_la_baja_si_aplica(self) -> None:
        from unittest.mock import patch

        from PyQt6.QtWidgets import QMessageBox

        from pos_uniformes.ui.helpers.inventario_acciones import TEXTO_CONFIRMAR_BAJA

        window, aplicar = self._precios({3: "250"})

        def elegir_bajar(caja) -> int:
            next(b for b in caja.buttons() if b.text() == TEXTO_CONFIRMAR_BAJA).click()
            return 0

        with patch.object(QMessageBox, "exec", new=elegir_bajar):
            window._handle_inventory_bulk_price_update()
        aplicar.assert_called_once()
        self.assertEqual(aplicar.call_args.kwargs["precios_por_variante"], [(3, Decimal("250"))])

    def test_si_nada_baja_el_flujo_queda_igual(self) -> None:
        from unittest.mock import patch

        from PyQt6.QtWidgets import QMessageBox

        window, aplicar = self._precios({3: "310", 4: "289"})
        vistas = []
        with patch.object(QMessageBox, "exec", new=lambda caja: vistas.append(caja) or 0):
            window._handle_inventory_bulk_price_update()
        self.assertEqual(vistas, [])
        aplicar.assert_called_once()

    def test_la_barra_de_lote_usa_el_mismo_camino(self) -> None:
        window = self._ventana()
        window._handle_inventory_bulk_price_update = Mock()
        window.inventario_pantalla.barra_lote.precio.setEnabled(True)
        window.inventario_pantalla.barra_lote.precio.click()
        window._handle_inventory_bulk_price_update.assert_called_once_with()

    def test_muchas_bajas_se_resumen(self) -> None:
        from pos_uniformes.services.inventario_precio_lote_service import MAXIMO_RENGLONES, precios_que_bajan
        from pos_uniformes.ui.helpers.inventario_acciones import armar_aviso_bajas

        filas = [_fila(i, 1, precio="300") for i in range(1, 31)]
        bajas = precios_que_bajan([(i, "250") for i in range(1, 31)], filas)
        caja, _ = armar_aviso_bajas(None, bajas)
        self.addCleanup(caja.deleteLater)
        self.assertIn("30 precios bajan", caja.text())
        self.assertIn(f"… y {30 - MAXIMO_RENGLONES} más", caja.text())
        self.assertEqual(caja.text().count("baja de"), MAXIMO_RENGLONES)
        self.assertNotIn("Show", " ".join(b.text() for b in caja.buttons()))

    # ── 1366 px ──────────────────────────────────────────────────────────

    def test_a_1366_nada_cortado_ni_scroll_de_mas(self) -> None:
        window = self._ventana()
        tabs = self._mostrar_a_1366(window)
        pantalla = window.inventario_pantalla
        ficha = pantalla.ficha
        pestana = tabs.currentWidget()
        self.assertEqual(pestana.verticalScrollBar().maximum(), 0)
        self.assertEqual(pestana.horizontalScrollBar().maximum(), 0)
        # La ficha vacía con «Para atender» y el bloque nuevo no se desplaza.
        self.assertEqual(ficha.scrolls[VACIA].verticalScrollBar().maximum(), 0)
        for widget in (ficha.acabarse_titulo, ficha.acabarse_nota, ficha.acabarse_boton):
            self.assertGreaterEqual(widget.width(), widget.fontMetrics().horizontalAdvance(widget.text()), widget.text())
        ficha.acabarse_boton.click()
        for _ in range(3):
            QApplication.processEvents()
        self.assertEqual(pestana.horizontalScrollBar().maximum(), 0)
        chip = pantalla.chip_acabarse
        self.assertGreaterEqual(chip.width(), chip.fontMetrics().horizontalAdvance(chip.text()))
        pantalla.chip_acabarse.click()
        pantalla.seleccionar(2)
        for _ in range(3):
            QApplication.processEvents()
        for widget in (ficha.venta, ficha.pedidas):
            self.assertGreaterEqual(widget.width(), widget.fontMetrics().horizontalAdvance(widget.text()), widget.text())


if __name__ == "__main__":
    unittest.main()
