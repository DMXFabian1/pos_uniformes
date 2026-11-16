"""El QR de descuento de temporada en la Venta Rápida (kiosko y POS).

Con Qt (offscreen) y sin base: la validación del código y la sesión se
sustituyen. Daniel, 2026-11-16: «Sí, con candados».
"""

from __future__ import annotations

import contextlib
import logging
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from pos_uniformes.services import descuento_qr_service as dqr

D = Decimal
QR = "DSCT-Codigo-De-Prueba-9"   # inventado para la prueba


def casual(precio="400", cantidad=1, sku="SC1"):
    return {"sku": sku, "nombre": "Sudadera casual", "talla": "M", "color": "", "precio": D(precio),
            "cantidad": cantidad, "categoria": "Ropa casual"}


def playera(sku="PO1"):
    return {"sku": sku, "nombre": "Playera polo", "talla": "8", "color": "", "precio": D("180"), "cantidad": 1,
            "categoria": "Oficial"}


@contextlib.contextmanager
def _sesion_falsa():
    yield SimpleNamespace()


class _Kiosko(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.contador = dqr.ContadorIntentos()
        p = patch.object(dqr, "CONTADOR", self.contador)
        p.start()
        self.addCleanup(p.stop)
        self.avisos: list[str] = []
        p2 = patch("pos_uniformes.ui.helpers.quick_sale_descuento_qr_helper.QMessageBox.warning",
                   side_effect=lambda _w, _t, texto: self.avisos.append(texto))
        p2.start()
        self.addCleanup(p2.stop)

    def _kiosko(self, items, *, en_linea=True, empleada="VEND-2"):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=not en_linea, _kiosk_lookup_from_cache=None,
                                            _db_online=en_linea))
        w._employee_code = empleada
        w._employee_name = "Fanny" if empleada else None
        w._biz_info = ("MAXIMODA", "", "")
        w._items = [dict(it) for it in items]
        return w

    def _escanear(self, w, texto=QR, *, resultado=dqr.VALIDO, pct=D("10")):
        with patch("pos_uniformes.database.connection.get_session", _sesion_falsa), \
                patch.object(dqr, "validar_codigo", return_value=resultado) as validar, \
                patch.object(type(w), "_elegir_pct_descuento_qr", return_value=pct):
            w._scan_input.setText(texto)
            w._on_scan_and_add()
        return validar


class EscaneoTests(_Kiosko):
    def test_qr_bueno_aplica_el_porcentaje(self) -> None:
        w = self._kiosko([casual(), playera()])
        validar = self._escanear(w)
        self.assertEqual(w._descuento_qr_pct, D("10"))
        self.assertEqual(w._compute_totals(), (D("580.00"), D("40.00"), D("540.00")))
        self.assertEqual(w._scan_input.text(), "")
        # El código va tal cual (sin mayúsculas) a validar, y no se agrega como SKU.
        self.assertEqual(validar.call_args[0][1], QR)
        self.assertEqual(len(w._items), 2)

    def test_sin_conexion_se_rechaza_sin_ir_a_la_base(self) -> None:
        w = self._kiosko([casual()], en_linea=False)
        validar = self._escanear(w)
        validar.assert_not_called()
        self.assertEqual(self.avisos, ["El QR de descuento necesita conexión"])
        self.assertIsNone(w._descuento_qr_pct)

    def test_sin_empleada_se_rechaza(self) -> None:
        w = self._kiosko([casual()], empleada=None)
        self._escanear(w).assert_not_called()
        self.assertEqual(self.avisos, [dqr.TXT_SIN_EMPLEADA])

    def test_codigo_conocido(self) -> None:
        w = self._kiosko([casual()])
        self._escanear(w, resultado=dqr.CODIGO_CONOCIDO)
        self.assertEqual(self.avisos, ["Cambia el código del QR en Configuración"])
        self.assertIsNone(w._descuento_qr_pct)

    def test_tres_equivocados_bloquean(self) -> None:
        w = self._kiosko([casual()])
        for _ in range(3):
            self._escanear(w, resultado=dqr.NO_VALIDO)
        self.assertTrue(self.contador.bloqueado())
        self.assertIn("Espera 5 min", self.avisos[-1])
        # Bloqueado: ni el bueno pasa, ni se consulta la base.
        self._escanear(w).assert_not_called()
        self.assertIsNone(w._descuento_qr_pct)

    def test_vencido(self) -> None:
        w = self._kiosko([casual()])
        with patch.object(dqr, "vencido", return_value=True):
            self._escanear(w).assert_not_called()
        self.assertEqual(self.avisos, ["El descuento de temporada terminó"])

    def test_el_codigo_escaneado_no_se_anota_en_el_log(self) -> None:
        w = self._kiosko([casual()])

        def _falla(*_a, **_k):
            raise RuntimeError(f"no conecta {QR}")

        with self.assertLogs(level=logging.DEBUG) as logs, \
                patch("pos_uniformes.database.connection.get_session", _sesion_falsa), \
                patch.object(dqr, "validar_codigo", side_effect=_falla):
            logging.getLogger("prueba").debug("inicio")
            w._scan_input.setText(QR)
            w._on_scan_and_add()
        self.assertFalse(any("Codigo-De-Prueba" in linea for linea in logs.output), logs.output)
        self.assertEqual(self.avisos, ["El QR de descuento necesita conexión"])


class DialogoTests(_Kiosko):
    def test_tres_botones_y_el_15_deshabilitado_bajo_600(self) -> None:
        w = self._kiosko([casual()])
        dlg = w._dialogo_pct_descuento_qr(dqr.opciones(D("400")))
        self.assertEqual([b.text() for b in dlg.botones], ["5 %", "10 %", "15 %"])
        self.assertEqual([b.isEnabled() for b in dlg.botones], [True, True, False])
        dlg.botones[1].click()
        self.assertEqual(dlg.pct_elegido, D("10"))

    def test_con_600_el_15_se_puede(self) -> None:
        w = self._kiosko([casual("300", 2)])
        self.assertEqual(w._base_ropa_normal(), D("600.00"))
        dlg = w._dialogo_pct_descuento_qr(dqr.opciones(w._base_ropa_normal()))
        self.assertTrue(dlg.botones[2].isEnabled())


class ChipTests(_Kiosko):
    def test_chip_visible_y_quitarlo(self) -> None:
        w = self._kiosko([casual()])
        self._escanear(w)
        self.assertFalse(w._chip_descuento_qr.isHidden())
        self.assertEqual(w._chip_descuento_qr.text(), "Descuento QR 10 %  ✕")
        w._chip_descuento_qr.click()
        self.assertIsNone(w._descuento_qr_pct)
        self.assertTrue(w._chip_descuento_qr.isHidden())
        self.assertEqual(w._compute_totals()[1], D("0.00"))

    def test_15_que_baja_a_10_lo_dice(self) -> None:
        w = self._kiosko([casual("300", 2)])
        self._escanear(w, pct=D("15"))
        self.assertIn("Descuento QR 15 %", w._chip_descuento_qr.text())
        w._items[0]["cantidad"] = 1            # el carrito cambió: $300
        w._refresh_totals()
        self.assertIn("Descuento QR 10 %", w._chip_descuento_qr.text())
        self.assertIn("15 % pide $600 de ropa normal; se aplicó 10 %", w._chip_descuento_qr.text())

    def test_al_terminar_la_venta_se_limpia(self) -> None:
        w = self._kiosko([casual()])
        self._escanear(w)
        w._vaciar_carrito()
        self.assertIsNone(w._descuento_qr_pct)
        self.assertTrue(w._chip_descuento_qr.isHidden())

    def test_al_salir_se_limpia(self) -> None:
        w = self._kiosko([casual()])
        self._escanear(w)
        w._on_logout()
        self.assertIsNone(w._descuento_qr_pct)


class TicketTests(_Kiosko):
    def test_renglon_y_lo_ahorrado(self) -> None:
        w = self._kiosko([casual(), playera()])
        self._escanear(w)
        texto = w._build_venta_text(fecha_str="16/11/2026 12:00")
        self.assertIn("Descuento autorizado 10 %:", texto)
        self.assertIn("-$40.00", texto)
        self.assertIn("¡Hoy ahorraste $40!", texto)
        self.assertNotIn("Codigo-De-Prueba", texto)

    def test_sin_qr_el_ticket_no_cambia(self) -> None:
        w = self._kiosko([casual(), playera()])
        texto = w._build_venta_text(fecha_str="16/11/2026 12:00")
        self.assertNotIn("Descuento autorizado", texto)
        self.assertNotIn("ahorraste", texto)

    def test_la_libreta_guarda_el_qr_en_la_fotografia(self) -> None:
        w = self._kiosko([casual(), playera()])
        self._escanear(w)
        with patch.object(type(w), "_tomar_folio_venta", return_value=None):
            entrada = w._armar_anotacion("venta", cliente=None, pago_tarjeta=False, anticipo=None,
                                         anticipo_tarjeta=False)[0]
        foto = entrada["calculo"]
        self.assertEqual(foto["entrada"]["descuento_qr_pct"], "10")
        self.assertEqual(foto["entrada"]["vendedora"], "VEND-2")
        self.assertEqual(foto["calculo"]["descuento_qr"]["importe"], "40.00")
        self.assertEqual(entrada["monto_total"], "540.00")
        self.assertNotIn("Codigo-De-Prueba", repr(entrada))

    def test_reimpresion_lee_el_qr_de_la_fotografia(self) -> None:
        from pos_uniformes.ui.views.quick_sale_view import _totales_de_fotografia

        fijo = _totales_de_fotografia({"calculo": {
            "subtotal": "580.00", "descuento_total": "40.00", "total": "540.00",
            "descuento_qr": {"pct": "10", "importe": "40.00"},
        }})
        self.assertEqual((fijo.qr_pct, fijo.qr_importe), (D("10"), D("40.00")))
        viejo = _totales_de_fotografia({"calculo": {"subtotal": "1", "descuento_total": "0", "total": "1"}})
        self.assertIsNone(viejo.qr_pct)


if __name__ == "__main__":
    unittest.main()
