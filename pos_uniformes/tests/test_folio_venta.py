"""Folio de la venta: QR en el ticket para encontrar la venta después.

Daniel (2026-11-12): «el QR era para identificar ventas, así si necesito
hacer un cambio o rastrear una venta».

Lo que se cuida: que el QR lleve la MISMA identidad con la que la venta
queda en la Libreta (si no, escanearlo no encuentra nada), que el lector con
teclado en español lo lea, que un SKU nunca se confunda con un folio, y que
escanearlo en el kiosko enseñe la venta en vez de agregarla al carrito.
"""

from __future__ import annotations

import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services import folio_venta_service as fv
from pos_uniformes.services.temporada_service import (
    MARCADOR_FIN,
    MARCADOR_INICIO,
    imagen_para_marcador,
    partir_marcador,
)

D = Decimal
U = "7f1f0599-fd10-4611-b2cb-cc62e92bdec8"


class FolioTests(unittest.TestCase):
    def test_codigo_y_folio_corto(self):
        self.assertEqual(fv.codigo_qr(U), "VTA7F1F0599FD104611B2CBCC62E92BDEC8")
        self.assertEqual(fv.folio_corto(U), "7F1F-0599")

    def test_el_qr_regresa_la_misma_venta(self):
        self.assertEqual(fv.uuid_de_codigo(fv.codigo_qr(U)), U)
        # El lector puede mandar minúsculas o espacios de más.
        self.assertEqual(fv.uuid_de_codigo("  " + fv.codigo_qr(U).lower() + " "), U)

    def test_un_sku_o_un_cliente_no_es_folio(self):
        for no in ("12345678", "PO1", "CLI-000015", "VEND-2", "VTA123", "", "ABCD12345"):
            self.assertFalse(fv.es_folio(no), no)
        self.assertTrue(fv.es_folio("7F1F-0599"))
        self.assertTrue(fv.es_folio("7f1f'0599"))   # el guion con teclado en español
        self.assertTrue(fv.es_folio(fv.codigo_qr(U)))

    def test_el_marcador_trae_el_dibujo_y_el_folio_escrito(self):
        m = fv.marcador_qr(U)
        self.assertTrue(m.startswith(MARCADOR_INICIO) and m.endswith(MARCADOR_FIN))
        nombre, respaldo = partir_marcador(m[len(MARCADOR_INICIO):-len(MARCADOR_FIN)])
        self.assertEqual(respaldo, "Folio: 7F1F-0599")
        ruta = imagen_para_marcador(nombre)
        self.assertIsNotNone(ruta)
        from PIL import Image

        with Image.open(ruta) as img:
            ancho, alto = img.size
        self.assertEqual(ancho, fv.ANCHO_RECUADRO)   # el recuadro, dentro del papel de 576
        self.assertTrue(180 <= alto <= 300)

    def test_un_marcador_qr_raro_no_da_imagen(self):
        self.assertIsNone(imagen_para_marcador("qr_VTA123"))
        self.assertIsNone(fv.png_para_marcador("logo"))


class BuscarVentaTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        ahora = datetime.now(timezone.utc)
        self.a = LibretaVenta(employee_code="VEND-2", employee_name="Fanny", tipo="venta", monto_total=D("450"),
                              operacion_uuid=U, created_at=ahora - timedelta(days=1), detalle=[])
        self.b = LibretaVenta(employee_code="VEND-2", employee_name="Fanny", tipo="venta", monto_total=D("100"),
                              operacion_uuid=str(uuid.uuid4()), created_at=ahora, detalle=[])
        self.s.add_all([self.a, self.b])
        self.s.flush()

    def test_por_qr(self):
        self.assertEqual(fv.buscar_venta(self.s, fv.codigo_qr(U)).id, self.a.id)

    def test_por_folio_corto(self):
        self.assertEqual(fv.buscar_venta(self.s, "7F1F-0599").id, self.a.id)
        self.assertEqual(fv.buscar_venta(self.s, "7f1f'0599").id, self.a.id)

    def test_no_existe(self):
        self.assertIsNone(fv.buscar_venta(self.s, fv.codigo_qr(str(uuid.uuid4()))))
        self.assertIsNone(fv.buscar_venta(self.s, "PO1"))


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _kiosko(self, online=True):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=not online, _kiosk_lookup_from_cache=None, _db_online=online))
        w._employee_code = "VEND-2"
        w._employee_name = "Fanny"
        w._items = [{"sku": "S1", "nombre": "Pants", "talla": "8", "color": "", "precio": D("450.00"), "cantidad": 1}]
        return w


class TicketConFolioTests(_Qt):
    def test_copia_del_cliente_lleva_qr_y_folio(self):
        texto = self._kiosko()._build_venta_text(folio=U)
        self.assertIn(fv.marcador_qr(U), texto)
        self.assertIn("Folio: 7F1F-0599", texto)

    def test_copia_de_la_tienda_solo_el_folio_escrito(self):
        texto = self._kiosko()._build_venta_text(store_copy=True, folio=U)
        self.assertNotIn(MARCADOR_INICIO + "qr_", texto)
        self.assertIn("Folio: 7F1F-0599", texto)

    def test_sin_folio_como_antes(self):
        self.assertNotIn("Folio:", self._kiosko()._build_venta_text())

    def test_la_reimpresion_lleva_el_mismo_qr(self):
        texto = self._kiosko().build_reprint_ticket(
            tipo="venta", detalle=[{"sku": "S1", "nombre": "Pants", "talla": "8", "precio": "450", "cantidad": 1}],
            cliente=None, employee_name="Fanny", descuento_empleada=False,
            created_at=datetime.now(timezone.utc), operacion_uuid=U,
        )
        self.assertIn(fv.marcador_qr(U), texto)


class LaLibretaGuardaElFolioImpresoTests(_Qt):
    def _anotacion(self, w):
        with patch.object(w, "_origen_satelite", return_value="Entrada"):
            (entrada,) = w._armar_anotacion("venta", cliente=None, pago_tarjeta=False, anticipo=None,
                                            anticipo_tarjeta=False)
        return entrada

    def test_la_venta_queda_con_el_folio_del_qr(self):
        w = self._kiosko()
        w._folio_venta = U
        self.assertEqual(self._anotacion(w)["operacion_uuid"], U)
        # Se usa una sola vez: la siguiente venta lleva otro.
        self.assertNotEqual(self._anotacion(w)["operacion_uuid"], U)

    def test_un_apartado_no_toma_el_folio_de_venta(self):
        w = self._kiosko()
        w._folio_venta = U
        self.assertIsNone(w._tomar_folio_venta("apartado"))
        self.assertEqual(w._tomar_folio_venta("venta"), U)

    def test_imprimir_venta_usa_el_mismo_folio_en_ticket_y_libreta(self):
        w = self._kiosko()
        capturado = {}

        def _route(_parent, _titulo, tickets, *, on_printed=None, on_back=None, **_kw):
            capturado["tickets"] = tickets
            capturado["on_printed"] = on_printed

        with patch.object(w, "_ask_venta_options", return_value=(False, False, False)), \
             patch.object(w, "_revisar_con_servidor", return_value=True), \
             patch("pos_uniformes.ui.views.quick_sale_view.route_tickets", side_effect=_route), \
             patch.object(w, "_registrar_y_vaciar", return_value=True) as registrar:
            w._on_ticket_venta()
            capturado["on_printed"]()
        folio = w._folio_venta
        self.assertIsNotNone(folio)
        self.assertIn(fv.marcador_qr(folio), capturado["tickets"][0])
        registrar.assert_called_once()
        self.assertEqual(w._tomar_folio_venta("venta"), folio)


class EscanearFolioTests(_Qt):
    def test_escanear_el_qr_abre_la_venta_y_no_agrega_al_carrito(self):
        w = self._kiosko()
        w._scan_input.setText(fv.codigo_qr(U))
        with patch.object(w, "_abrir_venta_por_folio") as abrir, patch.object(w, "add_sku") as add:
            w._on_scan_and_add()
        abrir.assert_called_once_with(fv.codigo_qr(U))
        add.assert_not_called()

    def test_un_sku_sigue_agregandose(self):
        w = self._kiosko()
        w._scan_input.setText("12345678")
        with patch.object(w, "_abrir_venta_por_folio") as abrir, patch.object(w, "add_sku") as add:
            w._on_scan_and_add()
        abrir.assert_not_called()
        add.assert_called_once()

    def test_sin_conexion_avisa(self):
        w = self._kiosko(online=False)
        with patch("PyQt6.QtWidgets.QMessageBox.information") as info, \
             patch.object(w, "_buscar_venta_por_folio") as buscar:
            w._abrir_venta_por_folio(fv.codigo_qr(U))
        buscar.assert_not_called()
        self.assertIn("Sin conexión", info.call_args.args[2])

    def test_no_encontrada_avisa(self):
        w = self._kiosko()
        with patch("PyQt6.QtWidgets.QMessageBox.information") as info, \
             patch.object(w, "_buscar_venta_por_folio", return_value=None):
            w._abrir_venta_por_folio(fv.codigo_qr(U))
        self.assertIn("No encontré", info.call_args.args[2])

    def _venta(self, **kw):
        base = dict(
            id=42, tipo="venta", operacion_uuid=U, created_at=datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc),
            employee_name="Fanny", employee_code="VEND-2", cliente="Ana López", descuento_empleada=False,
            monto_total=D("865"), monto_monedero=D("50"), pago_tarjeta=True,
            detalle=[{"nombre": "Pants", "talla": "8", "cantidad": 1, "precio": "450"},
                     {"nombre": "Playera", "talla": "10", "cantidad": 2, "precio": "207.50"}],
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def test_lo_que_se_le_ensena_de_la_venta(self):
        from pos_uniformes.ui.dialogs.venta_folio_dialog import datos_de_venta

        d = datos_de_venta(self._venta())
        self.assertEqual((d["folio"], d["tipo"], d["atendio"], d["cliente"]), ("7F1F-0599", "Venta #42", "Fanny", "Ana López"))
        self.assertEqual(d["piezas"], 3)
        self.assertEqual([a["importe"] for a in d["articulos"]], [D("450.00"), D("415.00")])
        self.assertEqual(d["pagos"], [("💳 Tarjeta", D("815.00")), ("👛 Monedero", D("50.00"))])
        d = datos_de_venta(self._venta(monto_monedero=None, pago_tarjeta=False, cliente=None))
        self.assertEqual(d["pagos"], [("💵 Efectivo", D("865.00"))])

    def test_la_ventana_y_su_boton_de_reimprimir(self):
        from pos_uniformes.ui.dialogs.venta_folio_dialog import VentaFolioDialog

        llamado = []
        dlg = VentaFolioDialog(self._venta(), al_reimprimir=lambda: llamado.append(True))
        self.assertIn("7F1F-0599", dlg.folio.text())
        self.assertEqual(dlg.total.text(), "$865.00")
        self.assertFalse(dlg.btn_reimprimir.isHidden())
        dlg.btn_reimprimir.click()
        self.assertEqual(llamado, [True])
        # Un abono no tiene ticket: no hay botón.
        abono = VentaFolioDialog(self._venta(tipo="abono"), al_reimprimir=lambda: None)
        self.assertTrue(abono.btn_reimprimir.isHidden())

    def test_encontrada_abre_la_ventana(self):
        w = self._kiosko()
        with patch.object(w, "_buscar_venta_por_folio", return_value=self._venta()), \
             patch("pos_uniformes.ui.dialogs.venta_folio_dialog.VentaFolioDialog.exec") as exec_:
            w._abrir_venta_por_folio(fv.codigo_qr(U))
        exec_.assert_called_once()


if __name__ == "__main__":
    unittest.main()
