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
                   return_value=(SimpleNamespace(monto_monedero=D("37.00")), MagicMock(), cashback)) as reg, \
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
        self.assertIn("Acumulado en esta compra", ticket)
        self.assertIn(tk_row("Saldo en monedero:", "$21.07"), ticket)
        self.assertIn(tk_row("Cliente:", "Ana"), ticket)
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


class ConfirmacionInciertaTest(_Base):
    """WALLET-001: si la red se cae mientras se confirma, la base pudo haber
    guardado. Reintentar NO debe descontar el saldo otra vez."""

    def _session_ctx(self, session):
        @contextmanager
        def _cm():
            yield session
        return _cm

    def _cobrar(self, w, session, **reg_kw):
        with patch.object(w, "_load_business_info", return_value=("MAXIMODA", "", "")), \
             patch.object(w, "_ask_venta_options", return_value=(False, False, False)), \
             patch("pos_uniformes.database.connection.get_session", self._session_ctx(session)), \
             patch("pos_uniformes.services.libreta_service.registrar_venta_con_monedero", **reg_kw) as reg, \
             patch("pos_uniformes.services.monedero_service.resumen_cliente",
                   return_value=SimpleNamespace(disponible=D("0.42"))), \
             patch.object(helper.QMessageBox, "warning") as aviso, \
             patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets") as route:
            w._on_ticket_venta()
        return reg, aviso, route

    def _venta_ok(self):
        return (SimpleNamespace(monto_monedero=D("37.00")), MagicMock(), SimpleNamespace(monto=D("20.65")))

    def test_corte_al_confirmar_avisa_y_el_reintento_usa_la_misma_identidad(self):
        w = self._widget()
        w._cliente = _cliente()
        w._usar_saldo = True
        caida = MagicMock()
        caida.commit.side_effect = OperationalError("commit", {}, Exception("down"))
        reg1, aviso, route = self._cobrar(w, caida, return_value=self._venta_ok())
        route.assert_not_called()
        self.assertIn("puede que SÍ haya quedado registrada", aviso.call_args.args[2])
        self.assertEqual(len(w._items), 1)           # el carrito queda para reintentar
        op1 = reg1.call_args.kwargs["operacion_uuid"]

        # Vuelve la red y se cobra otra vez, mismo carrito.
        reg2, _aviso, route2 = self._cobrar(w, MagicMock(), return_value=self._venta_ok())
        self.assertEqual(reg2.call_args.kwargs["operacion_uuid"], op1)
        route2.assert_called_once()
        self.assertEqual(w._items, [])

    def test_la_siguiente_venta_igual_es_otra_operacion(self):
        w = self._widget()
        w._cliente = _cliente()
        w._usar_saldo = True
        reg1, _a, _r = self._cobrar(w, MagicMock(), return_value=self._venta_ok())
        w._items = _items()
        w._cliente = _cliente()
        w._usar_saldo = True
        reg2, _a, _r = self._cobrar(w, MagicMock(), return_value=self._venta_ok())
        self.assertNotEqual(reg1.call_args.kwargs["operacion_uuid"], reg2.call_args.kwargs["operacion_uuid"])

    def test_cambiar_el_carrito_es_otra_operacion(self):
        w = self._widget()
        w._cliente = _cliente()
        w._usar_saldo = True
        caida = MagicMock()
        caida.commit.side_effect = OperationalError("commit", {}, Exception("down"))
        reg1, _a, _r = self._cobrar(w, caida, return_value=self._venta_ok())
        w._items.append({"sku": "SKU2", "nombre": "Playera", "talla": "8", "color": "",
                         "precio": D("150.00"), "cantidad": 1})
        reg2, _a, _r = self._cobrar(w, MagicMock(), return_value=self._venta_ok())
        self.assertNotEqual(reg1.call_args.kwargs["operacion_uuid"], reg2.call_args.kwargs["operacion_uuid"])

    def test_si_falla_leer_el_saldo_la_venta_igual_se_imprime(self):
        w = self._widget()
        w._cliente = _cliente()
        w._usar_saldo = True
        with patch.object(w, "_load_business_info", return_value=("MAXIMODA", "", "")), \
             patch.object(w, "_ask_venta_options", return_value=(False, False, False)), \
             patch("pos_uniformes.database.connection.get_session", self._session_ctx(MagicMock())), \
             patch("pos_uniformes.services.libreta_service.registrar_venta_con_monedero",
                   return_value=self._venta_ok()), \
             patch("pos_uniformes.services.monedero_service.resumen_cliente",
                   side_effect=OperationalError("saldo", {}, Exception("down"))), \
             patch.object(helper.QMessageBox, "warning") as aviso, \
             patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets") as route:
            w._on_ticket_venta()
        aviso.assert_not_called()
        route.assert_called_once()
        ticket = route.call_args.args[2][0]
        self.assertIn("Pagado con monedero", ticket)
        self.assertNotIn("Saldo en monedero", ticket)
        self.assertEqual(w._items, [])

    def test_el_ticket_dice_lo_que_cobro_la_base(self):
        """En un reintento la base devuelve el canje del primer intento."""
        w = self._widget()
        w._cliente = _cliente(disponible=D("50.00"))
        w._usar_saldo = True
        reg, _a, route = self._cobrar(
            w, MagicMock(),
            return_value=(SimpleNamespace(monto_monedero=D("37.00")), MagicMock(), None),
        )
        ticket = route.call_args.args[2][0]
        self.assertIn("-$37.00", ticket)
        self.assertIn("$413.00", ticket)


class TicketSinCanjeTest(_Base):
    """Daniel, 2026-11-11: el ticket dice cuánto acumuló y cómo queda el saldo."""

    def test_acumulado_y_saldo(self):
        w = self._widget()
        w._cliente = _cliente()                       # 5 %, saldo 37.42
        info = w._monedero_para_ticket(D("450"), False)
        self.assertEqual(info["cashback"], D("22.50"))
        self.assertEqual(info["saldo"], D("59.92"))
        texto = "\n".join(helper.lineas_ticket_monedero(info, tk_row))
        self.assertIn(tk_row("Acumulado en esta compra:", "$22.50"), texto)
        self.assertIn(tk_row("Saldo en monedero:", "$59.92"), texto)

    def test_nombre_y_nivel(self):
        w = self._widget()
        w._cliente = _cliente(programa="Maximoda Club")
        texto = "\n".join(helper.lineas_ticket_monedero(w._monedero_para_ticket(D("450"), False), tk_row))
        lineas = texto.split("\n")
        self.assertEqual(lineas[0], tk_row("Cliente:", "Ana"))
        self.assertEqual(lineas[1], tk_row("Nivel:", "Maximoda Club"))

    def test_nombre_largo_cabe(self):
        w = self._widget()
        w._cliente = _cliente(nombre="María Guadalupe Hernández Rodríguez", programa="Maximoda Profesional")
        lineas = helper.lineas_ticket_monedero(w._monedero_para_ticket(D("450"), False), tk_row)
        self.assertEqual(len(lineas[0]), 38)
        self.assertIn("María Guadalupe Hernández", lineas[0])

    def test_sin_programa_no_hay_renglon_de_nivel(self):
        w = self._widget()
        w._cliente = _cliente()
        texto = "\n".join(helper.lineas_ticket_monedero(w._monedero_para_ticket(D("450"), False), tk_row))
        self.assertIn("Cliente:", texto)
        self.assertNotIn("Nivel:", texto)

    def test_sin_conexion_solo_lo_acumulado(self):
        w = self._widget()
        w._cliente = _cliente(en_linea=False, disponible=D("0"))
        info = w._monedero_para_ticket(D("450"), False)
        self.assertIsNone(info["saldo"])
        self.assertNotIn("cliente", info)   # solo se sabe el código

    def test_sin_monedero_nada(self):
        w = self._widget()
        w._cliente = _cliente(tiene_monedero=False, tasa=None)
        self.assertIsNone(w._monedero_para_ticket(D("450"), False))

    def test_con_descuento_de_empleada_no_suma(self):
        """D1 (Daniel, 2026-11-11): con descuento de empleada no hay Monedero."""
        w = self._widget()
        w._cliente = _cliente()
        w._discount_active = True
        self.assertEqual(w._cashback_estimado(D("450"), D("0")), D("0.00"))
        info = w._monedero_para_ticket(D("450"), False)
        self.assertEqual(info["cashback"], D("0.00"))
        self.assertEqual(info["saldo"], D("37.42"))       # el saldo se sigue viendo
        w._pintar_cliente_bar()
        self.assertIn("no suma Monedero", w._cliente_label.text())
        self.assertNotIn("Gana", w._cliente_label.text())

    def test_sin_cliente_nada(self):
        w = self._widget()
        w._cliente = None
        self.assertIsNone(w._monedero_para_ticket(D("450"), False))


class VentasIgualesSeguidasTest(_Base):
    """WALLET-003: dos ventas iguales seguidas son dos ventas."""

    def test_dos_ventas_iguales_se_anotan_las_dos(self):
        w = self._widget(online=False)
        with patch("pos_uniformes.services.libreta_local_queue_service.encolar_operacion") as enc, \
             patch.object(w, "_drenar_libreta_en_background"):
            w._registrar_y_vaciar("venta")
            w._items = _items()
            w._registrar_y_vaciar("venta")
        self.assertEqual(enc.call_count, 2)
        uuids = {c.args[0]["operacion_uuid"] for c in enc.call_args_list}
        self.assertEqual(len(uuids), 2)

    def test_carrito_vacio_no_se_anota(self):
        w = self._widget(online=False)
        w._items = []
        with patch("pos_uniformes.services.libreta_local_queue_service.encolar_operacion") as enc, \
             patch.object(w, "_drenar_libreta_en_background"):
            w._registrar_en_libreta("venta")
        enc.assert_not_called()


class TicketTest(unittest.TestCase):
    def test_lineas_del_monedero(self):
        lineas = helper.lineas_ticket_monedero(
            {"canje": D("37"), "por_cobrar": D("413"), "metodo": "Efectivo", "cashback": D("20.65"), "saldo": D("21.07")},
            tk_row,
        )
        texto = "\n".join(lineas)
        for esperado in ("Pagado con monedero", "-$37.00", "Efectivo:", "$413.00", "Acumulado en esta compra", "$20.65", "$21.07"):
            self.assertIn(esperado, texto)

    def test_por_la_cola_sin_saldo_conocido(self):
        texto = "\n".join(helper.lineas_ticket_monedero({"cashback": D("5"), "cashback_pendiente": True}, tk_row))
        self.assertIn(tk_row("Acumulado en esta compra:", "$5.00"), texto)
        self.assertNotIn("Saldo", texto)

    def test_sin_cashback_no_hay_renglon_de_acumulado(self):
        texto = "\n".join(helper.lineas_ticket_monedero({"cashback": D("0"), "saldo": D("12")}, tk_row))
        self.assertNotIn("Acumulado", texto)
        self.assertIn(tk_row("Saldo en monedero:", "$12.00"), texto)


if __name__ == "__main__":
    unittest.main()
