"""La pantalla del cambio y su ticket (Daniel, 2026-11-12).

La ventana arma el cambio y enseña la cuenta; el kiosko lo registra (Libreta,
stock y Monedero) e imprime el ticket del cambio.
"""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services import cambio_service as cs
from pos_uniformes.tests.test_cambio_service import _Base

D = Decimal


def _renglones():
    return [
        cs.RenglonVendido(0, "S1", "Pants", "8", 1, 0, D("450"), False),
        cs.RenglonVendido(1, "S2", "Playera", "10", 2, 1, D("200"), False),
    ]


def _datos():
    return {"folio": "7F1F-0599", "cuando": "12/11/2026 · 12:00", "atendio": "Fanny"}


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])


class CambioDialogTests(_Qt):
    def _dialogo(self, **kw):
        from pos_uniformes.ui.dialogs.cambio_dialog import CambioDialog

        args = dict(
            datos_venta=_datos(), renglones=_renglones(), abono=D("0"), ya_quitado=D("0"), dias=3,
            cliente=None, buscar_producto=lambda sku: {"sku": sku, "nombre": "Pants", "talla": "10", "precio": D("450")},
            elegir_cliente=lambda: (7, "Ana"), es_dueno=lambda c: c == "VEND-1", registrar=lambda d: None,
        )
        args.update(kw)
        return CambioDialog(**args)

    def test_sin_regresar_nada_no_se_puede(self):
        dlg = self._dialogo()
        self.assertFalse(dlg.btn_hacer.isEnabled())
        self.assertEqual(dlg.resultado.text(), "Elige qué regresa")

    def test_no_regresa_mas_de_lo_que_queda(self):
        dlg = self._dialogo()
        for _ in range(3):
            dlg._mover(1, +1)
        self.assertEqual(dlg.regresa, {1: 1})   # vendió 2, ya cambió 1
        dlg._mover(1, -1)
        self.assertEqual(dlg.regresa, {})

    def test_misma_prenda_otra_talla_queda_parejo(self):
        dlg = self._dialogo()
        dlg._mover(0, +1)
        dlg.escaner.setText("S9")
        dlg._escanear()
        self.assertEqual(dlg.resultado.text(), "Queda parejo")
        self.assertTrue(dlg.btn_hacer.isEnabled())

    def test_paga_la_diferencia_con_tarjeta(self):
        recibido = []
        dlg = self._dialogo(registrar=lambda d: recibido.append(d))
        dlg._mover(1, +1)
        dlg.agregar({"sku": "S9", "nombre": "Pants", "talla": "10", "precio": D("450")})
        self.assertEqual(dlg.resultado.text(), "Paga $250.00")
        self.assertFalse(dlg.btn_tarjeta.isHidden())
        dlg.btn_tarjeta.click()
        dlg.btn_hacer.click()
        self.assertEqual(recibido[0]["regresa"], {1: 1})
        self.assertTrue(recibido[0]["pago_tarjeta"])
        self.assertEqual(recibido[0]["lleva"][0]["cantidad"], 1)

    def test_a_favor_pide_cliente_y_quita_el_monedero_ganado(self):
        dlg = self._dialogo(abono=D("45"), renglones=[cs.RenglonVendido(0, "S1", "Pants", "8", 1, 0, D("450"), False)])
        dlg._mover(0, +1)
        self.assertEqual(dlg.resultado.text(), "A favor $405.00 → Monedero")
        self.assertFalse(dlg.btn_hacer.isEnabled())
        self.assertFalse(dlg.btn_cliente.isHidden())
        dlg.btn_cliente.click()
        self.assertTrue(dlg.btn_hacer.isEnabled())
        self.assertIn("Ana", dlg.ficha_cliente.text())

    def test_fuera_de_plazo_solo_con_el_gafete_del_dueno(self):
        dlg = self._dialogo(dias=20)
        dlg._mover(0, +1)
        dlg.agregar({"sku": "S9", "nombre": "Pants", "talla": "10", "precio": D("450")})
        self.assertFalse(dlg.aviso_plazo.isHidden())
        self.assertFalse(dlg.btn_hacer.isEnabled())
        with patch("pos_uniformes.ui.dialogs.cambio_dialog.QMessageBox.warning") as aviso:
            dlg.gafete.setText("VEND-2")
            dlg._autorizar()
        aviso.assert_called_once()
        dlg.gafete.setText("VEND-1")
        dlg._autorizar()
        self.assertTrue(dlg.btn_hacer.isEnabled())

    def test_liquidacion_sin_cambio_salvo_el_dueno(self):
        """2026-11-12 (Daniel: «solucionemos estos»)."""
        recibido = []
        renglones = [
            cs.RenglonVendido(0, "S1", "Pants", "8", 1, 0, D("200"), True, liquidacion=True),
            cs.RenglonVendido(1, "S2", "Playera", "10", 1, 0, D("200"), True),   # Oferta
        ]
        dlg = self._dialogo(renglones=renglones, registrar=lambda d: recibido.append(d))
        self.assertFalse(dlg.aviso_plazo.isHidden())
        self.assertIn("Liquidación", dlg.texto_plazo.text())
        self.assertFalse(dlg._botones[0][1].isEnabled())
        self.assertTrue(dlg._botones[1][1].isEnabled())
        dlg._mover(0, +1)
        self.assertEqual(dlg.regresa, {})
        dlg._mover(1, +1)                       # la de Oferta sí
        dlg.agregar({"sku": "S9", "nombre": "Pants", "talla": "10", "precio": D("200")})
        self.assertTrue(dlg.btn_hacer.isEnabled())
        dlg.gafete.setText("VEND-1")
        dlg._autorizar()
        self.assertTrue(dlg._botones[0][1].isEnabled())
        dlg._mover(0, +1)
        self.assertEqual(dlg.regresa, {1: 1, 0: 1})
        dlg.agregar({"sku": "S9", "nombre": "Pants", "talla": "10", "precio": D("200")})
        dlg.btn_hacer.click()
        self.assertTrue(recibido[0]["autorizo_dueno"])

    def test_si_falla_al_registrar_se_avisa_y_no_cierra(self):
        dlg = self._dialogo(registrar=lambda d: "No hay stock")
        dlg._mover(0, +1)
        dlg.agregar({"sku": "S9", "nombre": "Pants", "talla": "10", "precio": D("450")})
        with patch("pos_uniformes.ui.dialogs.cambio_dialog.QMessageBox.warning") as aviso:
            dlg._hacer()
        aviso.assert_called_once()
        self.assertEqual(dlg.result(), 0)


class VentaFolioConCambioTests(_Qt):
    def test_el_boton_solo_en_ventas(self):
        from datetime import datetime, timezone

        from pos_uniformes.ui.dialogs.venta_folio_dialog import VentaFolioDialog

        venta = SimpleNamespace(
            id=1, tipo="venta", operacion_uuid=None, created_at=datetime(2026, 11, 12, tzinfo=timezone.utc),
            employee_name="Fanny", employee_code="VEND-2", cliente=None, descuento_empleada=False,
            monto_total=D("450"), monto_monedero=None, pago_tarjeta=False, detalle=[],
        )
        llamado = []
        dlg = VentaFolioDialog(venta, al_cambiar=lambda: llamado.append(True))
        self.assertFalse(dlg.btn_cambiar.isHidden())
        dlg.btn_cambiar.click()
        self.assertEqual(llamado, [True])
        venta.tipo = "apartado"
        apartado = VentaFolioDialog(venta, al_cambiar=lambda: None)
        self.assertTrue(apartado.btn_cambiar.isHidden())


class CambioDesdeElKioskoTests(_Base):
    """De punta a punta: la ventana, el registro en la base y el ticket."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _kiosko(self):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-3"
        w._employee_name = "Lupita"
        return w

    def test_cambio_con_saldo_a_favor_imprime_su_ticket(self):
        from pos_uniformes.ui.dialogs.cambio_dialog import CambioDialog

        venta = self._venta([self._linea(self.v[0], "450")], "450", cliente=True)
        sesion = self.s

        @contextmanager
        def get_session():
            yield sesion

        nueva = self._linea(self.v[1], "200")
        nueva.pop("cantidad")

        def usar(dlg):
            dlg._mover(0, +1)
            dlg.agregar(nueva)
            dlg._hacer()
            return 1

        w = self._kiosko()
        with patch("pos_uniformes.database.connection.get_session", get_session), \
             patch.object(w, "_en_linea", return_value=True), \
             patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")), \
             patch.object(CambioDialog, "exec", usar), \
             patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets") as imprimir:
            w._hacer_cambio(venta)
        imprimir.assert_called_once()
        ticket = imprimir.call_args.args[2][0]
        self.assertIn("Ticket de cambio", ticket)
        self.assertIn("REGRESA", ticket)
        self.assertIn("SE LLEVA", ticket)
        self.assertIn("A FAVOR EN MONEDERO", ticket)
        self.assertIn("$205.00", ticket)
        self.assertIn("$250.00", ticket)        # saldo: 45 + 205
        self.assertEqual(self._stock(self.v[0]), 3)
        self.assertEqual(self._stock(self.v[1]), 2)
        self.assertEqual(self._saldo(), D("250.00"))


if __name__ == "__main__":
    unittest.main()
