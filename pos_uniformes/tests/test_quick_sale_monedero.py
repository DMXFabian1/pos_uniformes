"""Venta rápida con monedero: QR del cliente, usar saldo y cashback.

Lo que no debe pasar: canjear sin conexión, canjear con un cliente que solo
se buscó por nombre, perder el carrito si el canje falla, o que la siguiente
venta herede al cliente.
"""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from sqlalchemy.exc import OperationalError

from pos_uniformes.ui.helpers import quick_sale_monedero_helper as helper
from pos_uniformes.ui.helpers.ticket_print_layout_helper import tk_row
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

_MOD = "pos_uniformes.ui.views.quick_sale_view"
D = Decimal


def _items():
    return [{"sku": "SKU1", "nombre": "Pants", "talla": "6", "color": "", "precio": D("450.00"), "cantidad": 1}]


def _cliente(**kw):
    base = {
        "id": 7, "codigo": "CLI-000007", "nombre": "Ana", "por_qr": True, "en_linea": True,
        "tiene_monedero": True, "estado": "activo", "disponible": D("37.42"), "tasa": D("5"),
        "proximo_vencimiento": None, "monto_proximo_vencimiento": D("0"),
    }
    base.update(kw)
    return base


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _widget(self, online=True):
        sat = SimpleNamespace(offline_mode=not online, _kiosk_lookup_from_cache=None, _db_online=online)
        w = QuickSaleWidget(sat)
        w._employee_code = "VEND-2"
        w._employee_name = "Fanny"
        w._items = _items()
        return w


class EscaneoTest(_Base):
    def test_qr_de_cliente_no_se_agrega_como_producto(self):
        w = self._widget()
        w._scan_input.setText("cli'000007")   # teclado español: - llega como '
        with patch.object(w, "_identificar_cliente") as ident, patch.object(w, "add_sku") as add:
            w._on_scan_and_add()
        ident.assert_called_once_with("CLI-000007", por_qr=True)
        add.assert_not_called()

    def test_sin_conexion_guarda_el_codigo_y_no_deja_usar_saldo(self):
        w = self._widget(online=False)
        w._identificar_cliente("CLI-000007", por_qr=True)
        self.assertEqual(w._cliente["codigo"], "CLI-000007")
        self.assertFalse(w._cliente["en_linea"])
        self.assertFalse(w._btn_usar_saldo.isEnabled())
        self.assertEqual(w._canje_actual(D("450")), D("0.00"))

    def test_la_cola_lleva_identidad_y_cliente(self):
        w = self._widget(online=False)
        w._identificar_cliente("CLI-000007", por_qr=True)
        with patch("pos_uniformes.services.libreta_local_queue_service.encolar_operacion") as enc, \
             patch.object(w, "_drenar_libreta_en_background"):
            w._registrar_y_vaciar("venta")
        entry = enc.call_args.args[0]
        self.assertEqual(entry["cliente_codigo"], "CLI-000007")
        self.assertIsNone(entry["cliente_id"])
        self.assertEqual(len(entry["operacion_uuid"]), 36)
        self.assertIsNone(w._cliente)   # la siguiente venta no lo hereda


class CanjeTest(_Base):
    def test_ajusta_el_saldo_al_redondeo(self):
        w = self._widget()
        w._cliente = _cliente()
        w._usar_saldo = True
        self.assertEqual(w._canje_actual(D("450")), D("37.00"))
        self.assertEqual(w._cashback_estimado(D("450"), D("37")), D("20.65"))

    def test_buscado_por_nombre_no_canjea(self):
        w = self._widget()
        w._cliente = _cliente(por_qr=False)
        w._usar_saldo = True
        self.assertEqual(w._canje_actual(D("450")), D("0.00"))

    def test_bloqueado_no_canjea(self):
        w = self._widget()
        w._cliente = _cliente(estado="bloqueado")
        w._usar_saldo = True
        self.assertEqual(w._canje_actual(D("450")), D("0.00"))

    def _session_ctx(self, session):
        @contextmanager
        def _cm():
            yield session
        return _cm

    def test_venta_con_saldo_se_confirma_antes_de_imprimir(self):
        w = self._widget()
        w._cliente = _cliente()
        w._usar_saldo = True
        session = MagicMock()
        cashback = SimpleNamespace(monto=D("20.65"))
        with patch.object(w, "_load_business_info", return_value=("MAXIMODA", "", "")), \
             patch.object(w, "_ask_venta_options", return_value=(False, False, False)), \
             patch("pos_uniformes.database.connection.get_session", self._session_ctx(session)), \
             patch("pos_uniformes.services.libreta_service.registrar_venta_con_monedero",
                   return_value=(MagicMock(), MagicMock(), cashback)) as reg, \
             patch("pos_uniformes.services.monedero_service.resumen_cliente",
                   return_value=SimpleNamespace(disponible=D("21.07"))), \
             patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets") as route, \
             patch(f"{_MOD}.route_tickets") as route_cola, \
             patch.object(w, "_registrar_en_libreta") as cola:
            w._on_ticket_venta()
        self.assertEqual(reg.call_args.kwargs["monto_monedero"], D("37.00"))
        self.assertEqual(reg.call_args.kwargs["cliente_id"], 7)
        session.commit.assert_called_once()
        cola.assert_not_called()          # no pasa por la cola offline
        route_cola.assert_not_called()
        ticket = route.call_args.args[2][0]
        self.assertIn("Pagado con monedero", ticket)
        self.assertIn("413.00", ticket)
        self.assertIn("Cashback ganado", ticket)
        self.assertEqual(w._items, [])
        self.assertIsNone(w._cliente)

    def test_si_se_cae_la_red_no_se_registra_y_el_carrito_queda(self):
        w = self._widget()
        w._cliente = _cliente()
        w._usar_saldo = True
        session = MagicMock()
        with patch.object(w, "_ask_venta_options", return_value=(False, False, False)), \
             patch("pos_uniformes.database.connection.get_session", self._session_ctx(session)), \
             patch("pos_uniformes.services.libreta_service.registrar_venta_con_monedero",
                   side_effect=OperationalError("x", {}, Exception("down"))), \
             patch.object(helper.QMessageBox, "warning") as aviso, \
             patch(f"{_MOD}.route_tickets") as route:
            w._on_ticket_venta()
        route.assert_not_called()
        session.rollback.assert_called_once()
        self.assertIn("conectada al servidor", aviso.call_args.args[2])
        self.assertEqual(len(w._items), 1)
        self.assertIsNotNone(w._cliente)

    def test_kiosko_sin_conexion_ni_lo_intenta(self):
        w = self._widget()
        w._cliente = _cliente()
        w._usar_saldo = True
        w.satellite._db_online = False
        with patch.object(w, "_ask_venta_options", return_value=(False, False, False)), \
             patch("pos_uniformes.services.libreta_service.registrar_venta_con_monedero") as reg, \
             patch.object(helper.QMessageBox, "warning"):
            w._on_ticket_venta()
        reg.assert_not_called()
        self.assertEqual(len(w._items), 1)


class TicketTest(unittest.TestCase):
    def test_lineas_del_monedero(self):
        lineas = helper.lineas_ticket_monedero(
            {"canje": D("37"), "por_cobrar": D("413"), "metodo": "Efectivo", "cashback": D("20.65"), "saldo": D("21.07")},
            tk_row,
        )
        texto = "\n".join(lineas)
        for esperado in ("Pagado con monedero", "-$37.00", "Efectivo:", "$413.00", "Cashback ganado", "$21.07"):
            self.assertIn(esperado, texto)

    def test_pendiente_si_va_por_la_cola(self):
        texto = "\n".join(helper.lineas_ticket_monedero({"cashback": D("5"), "cashback_pendiente": True}, tk_row))
        self.assertIn("al sincronizar", texto)
        self.assertNotIn("monedero:", texto)


if __name__ == "__main__":
    unittest.main()
