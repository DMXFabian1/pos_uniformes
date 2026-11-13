"""El kiosko deja la compra a cuenta en una sola transacción (2026-11-12).

`_al_imprimir` usa `compra_a_cuenta_service.registrar_venta_a_cuenta`; si
falla, avisa que la copia «a cuenta» no vale y anota la venta en efectivo
con el mismo folio. Antes de imprimir revisa que todavía le quepa.
"""

from __future__ import annotations

import os
import unittest
from datetime import date
from decimal import Decimal as D
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services import compra_a_cuenta_service as cac

SAB14 = date(2026, 11, 14)
FOLIO = "abcdef12-0000-4000-8000-000000000001"


class KioskoTests(unittest.TestCase):
    """El kiosko usa la transacción única y, si falla, no la deja «a cuenta»."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _kiosko(self):
        from types import SimpleNamespace

        from pos_uniformes.services import incentivo_empleada_service as inc
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code, w._employee_name = "VEND-2", "Fanny"
        w._poner_categorias = lambda items: None
        w._items = [{"sku": "S1", "nombre": "Pants", "talla": "8", "color": "", "precio": D("450.00"), "cantidad": 1}]
        w._discount_active = True
        w._compradora = inc.EstadoCompradora("VEND-3", "Cristal", D("20"), D("3000"), D("0"))
        w._refresh_totals()
        w._folio_venta = FOLIO
        return w

    def _correr(self, w, **registrar):
        opcion = cac.opciones_de_pago(SAB14, 7)[0]
        anotadas = []
        with patch("pos_uniformes.database.connection.get_session"), \
             patch.object(cac, "registrar_venta_a_cuenta", **registrar) as reg, \
             patch.object(cac, "avisar_a_daniel"), \
             patch.object(w, "_anotar", side_effect=lambda entradas, **_k: anotadas.append(entradas) or True), \
             patch("pos_uniformes.ui.helpers.quick_sale_compradora_helper.QMessageBox.warning") as aviso:
            self.assertTrue(w._anotar_a_cuenta(opcion))
        return reg, anotadas, aviso

    def test_con_conexion_va_en_una_sola_transaccion(self):
        w = self._kiosko()
        reg, anotadas, aviso = self._correr(w, return_value=object())
        kw = reg.call_args.kwargs
        self.assertEqual((kw["employee_code"], kw["creado_por"]), ("VEND-3", "VEND-2"))
        self.assertEqual((kw["entrada"]["operacion_uuid"], kw["entrada"]["compradora_code"]), (FOLIO, "VEND-3"))
        self.assertEqual((anotadas, w._items), ([], []))
        aviso.assert_not_called()

    def test_si_falla_avisa_que_la_copia_no_vale_y_la_anota_en_efectivo(self):
        w = self._kiosko()
        _reg, anotadas, aviso = self._correr(w, side_effect=RuntimeError("sin red"))
        self.assertIn("NO vale", aviso.call_args.args[2])
        # Misma foto, mismo folio del ticket: la venta no se pierde ni se duplica.
        self.assertEqual([e["operacion_uuid"] for e in anotadas[0]], [FOLIO])
        self.assertFalse(anotadas[0][0]["pago_tarjeta"])
        self.assertEqual(w._items, [])

    def test_antes_de_imprimir_revisa_que_quepa(self):
        w = self._kiosko()
        with patch("pos_uniformes.database.connection.get_session"), \
             patch.object(cac, "puede_dejarse_a_cuenta", return_value="A cuenta le caben $10.00"), \
             patch("pos_uniformes.ui.helpers.quick_sale_compradora_helper.QMessageBox.warning") as aviso:
            self.assertFalse(w._revisar_a_cuenta(D("450")))
        self.assertIn("No se imprimió nada", aviso.call_args.args[2])
        with patch("pos_uniformes.database.connection.get_session", side_effect=RuntimeError("sin red")), \
             patch("pos_uniformes.ui.helpers.quick_sale_compradora_helper.QMessageBox.warning"):
            self.assertFalse(w._revisar_a_cuenta(D("450")))


if __name__ == "__main__":
    unittest.main()
