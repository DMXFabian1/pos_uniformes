"""La caja de Venta rápida rediseñada (Daniel, 2026-11-12).

«Apliqué el descuento de empleada y no sé de quién ni qué» y «mejorar esta
vista ya teniendo en cuenta todos los cambios». A la izquierda escanear y el
carrito; a la derecha Cliente y el Total con desglose. Luego: «no me gustaría
que las personas ajenas vean que las empleadas tienen su descuento propio»: se
pone desde el menú «⋯» y en pantalla solo dice «Precio especial».
"""

from __future__ import annotations

import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services import incentivo_empleada_service as inc

D = Decimal
CRISTAL = inc.EstadoCompradora("VEND-3", "Cristal", D("20"), D("3000"), D("0"))


class CajaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _kiosko(self, items=None):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code, w._employee_name = "VEND-2", "Fanny"
        w._poner_categorias = lambda items: None
        w._items = items or []
        w._refresh_totals()
        return w

    def _pants(self, cantidad=1):
        return {"sku": "S1", "nombre": "Pants", "talla": "8", "color": "", "precio": D("450.00"), "cantidad": cantidad}

    def test_cada_cosa_en_su_columna(self):
        w = self._kiosko()
        self.assertTrue(w._discount_check.isHidden())   # el interruptor ya no se ve
        self.assertFalse(w._sin_cliente.isHidden())
        self.assertTrue(w._compradora_texto.isHidden())
        self.assertTrue(w._chip_precio_especial.isHidden())
        self.assertEqual(w._accion_precio_especial.text(), "🔒  Precio especial")
        self.assertTrue(w._sin_cliente.isAncestorOf(w._btn_cliente))

    def test_el_menu_pone_y_quita_el_precio_especial(self):
        w = self._kiosko([self._pants()])
        with patch.object(w, "_authorize_owner", return_value=True), \
             patch.object(w, "_elegir_compradora", side_effect=lambda: setattr(w, "_compradora", CRISTAL)):
            w._accion_precio_especial.trigger()
        self.assertTrue(w._discount_active)
        self.assertFalse(w._chip_precio_especial.isHidden())
        self.assertEqual(w._chip_precio_especial.text(), "🔒  Precio especial")
        self.assertIn("Cristal", w._compradora_texto.text())
        self.assertIn("20 %", w._compradora_texto.text())
        self.assertIn("$3,000.00", w._compradora_texto.text())
        self.assertEqual(w._accion_precio_especial.text(), "🔓  Quitar precio especial")
        # A la vista del cliente no dice ni «empleada» ni su nombre.
        self.assertEqual(w._filas_total["descuento"][1].text(), "Precio especial")
        self.assertFalse(w._filas_total["subtotal"][0].isHidden())
        # El detalle no está en ninguna parte de la pantalla de la caja.
        self.assertFalse(w.isAncestorOf(w._compradora_texto))
        w._accion_precio_especial.trigger()   # se quita
        self.assertFalse(w._discount_active)
        self.assertTrue(w._compradora_texto.isHidden())
        self.assertTrue(w._filas_total["descuento"][0].isHidden())
        self.assertTrue(w._chip_precio_especial.isHidden())

    def test_la_ficha_le_ensena_a_quien_cobra_y_lo_quita(self):
        from PyQt6.QtCore import QTimer

        w = self._kiosko([self._pants()])
        with patch.object(w, "_authorize_owner", return_value=True), \
             patch.object(w, "_elegir_compradora", side_effect=lambda: setattr(w, "_compradora", CRISTAL)):
            w._accion_precio_especial.trigger()
        vista = {}

        def _quitar():
            dlg = w._dialogo_precio_especial
            vista["texto"] = " ".join(l.text() for l in dlg.findChildren(type(w._compradora_texto)))
            dlg.done(2)

        QTimer.singleShot(0, _quitar)
        w._chip_precio_especial.click()
        self.assertIn("Cristal", vista["texto"])
        self.assertFalse(w._discount_active)

    def test_sin_compradora_lo_dice(self):
        w = self._kiosko([self._pants()])
        with patch.object(w, "_authorize_owner", return_value=True), \
             patch.object(w, "_elegir_compradora", return_value=None):
            w._accion_precio_especial.trigger()
        self.assertIn("sin compradora", w._compradora_texto.text())

    def test_sin_descuento_no_hay_desglose(self):
        w = self._kiosko([self._pants(2)])
        self.assertEqual(w._total_label.text(), "$900.00")
        self.assertEqual(w._total_meta.text(), "1 linea  ·  2 piezas")
        for fila, _e, _v in w._filas_total.values():
            self.assertTrue(fila.isHidden())

    def test_con_saldo_dice_lo_que_se_cobra(self):
        w = self._kiosko([self._pants()])
        with patch.object(w, "_canje_actual", return_value=D("120.00")):
            w._refresh_totals()
        self.assertEqual(w._filas_total["saldo"][2].text(), "−$120.00")
        self.assertIn("$330.00", w._filas_total["por_cobrar"][2].text())
        self.assertTrue(w._filas_total["subtotal"][0].isHidden())


if __name__ == "__main__":
    unittest.main()
