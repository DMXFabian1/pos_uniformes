"""Tests de venta rapida: impresion en un solo dialogo y carga de info.

- Un solo clic en "Ticket Venta" / "Ticket Apartado" abre UN dialogo con
  todos los tickets (antes abria uno por copia -> dos clics).
- _load_business_info evita pegar a la DB cuando esta offline (antes
  bloqueaba hasta el connect_timeout de 5s en cada ticket).
"""

from __future__ import annotations

import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QLineEdit

from pos_uniformes.ui.helpers.ticket_print_layout_helper import tk_row
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

_MOD = "pos_uniformes.ui.views.quick_sale_view"


def _items() -> list[dict]:
    return [
        {"sku": "SKU004838", "nombre": "Pants", "talla": "6", "color": "",
         "precio": Decimal("515.00"), "cantidad": 1},
    ]


class QuickSaleTicketDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _make_widget(self, offline: bool = True) -> QuickSaleWidget:
        satellite = SimpleNamespace(offline_mode=offline, _kiosk_lookup_from_cache=None)
        widget = QuickSaleWidget(satellite)
        widget._employee_code = "VEND-1"
        widget._employee_name = "Daniel Fabian"
        widget._items = _items()
        return widget

    def test_venta_default_prints_only_customer_ticket(self) -> None:
        # Default: sin copia — la empleada contestó "Solo ticket del cliente".
        widget = self._make_widget()
        widget._discount_active = False
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch.object(widget, "_ask_venta_options", return_value=(False, False)), \
                patch(f"{_MOD}.route_tickets") as opd:
            widget._on_ticket_venta()
        opd.assert_called_once()
        tickets = opd.call_args.args[2]
        self.assertEqual(len(tickets), 1)

    def test_venta_with_copy_confirmed_prints_store_copy(self) -> None:
        widget = self._make_widget()
        widget._discount_active = False
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch.object(widget, "_ask_venta_options", return_value=(True, False)), \
                patch(f"{_MOD}.route_tickets") as opd:
            widget._on_ticket_venta()
        opd.assert_called_once()
        tickets = opd.call_args.args[2]
        self.assertEqual(len(tickets), 2)
        self.assertIn("COPIA TIENDA", tickets[1])
        # Efectivo: la copia lleva el precio normal.
        self.assertIn("$515.00", tickets[1])

    def test_venta_con_tarjeta_imprime_copia_con_comision(self) -> None:
        # Contestó "con tarjeta": la copia sale con el 4.5% ya descontado
        # automáticamente — sin checkbox en el diálogo de impresión.
        widget = self._make_widget()
        widget._discount_active = False
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch.object(widget, "_ask_venta_options", return_value=(True, True)), \
                patch.object(widget, "_registrar_en_libreta") as registrar, \
                patch(f"{_MOD}.route_tickets") as opd:
            widget._on_ticket_venta()
            # El registro en la Libreta espera a que la impresión arranque.
            registrar.assert_not_called()
            opd.call_args.kwargs["on_printed"]()
        tickets = opd.call_args.args[2]
        self.assertEqual(len(tickets), 2)
        # 515.00 - 4.5% = 491.82 -> regla de redondeo -> 492.00
        self.assertIn("$492.00", tickets[1])
        self.assertNotIn("515.00", tickets[1])
        # El del cliente NO cambia.
        self.assertIn("$515.00", tickets[0])
        registrar.assert_called_once_with("venta", cliente=None, pago_tarjeta=True)

    def test_venta_with_discount_prints_two_tickets_one_dialog(self) -> None:
        widget = self._make_widget()
        widget._discount_active = True
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch.object(widget, "_ask_venta_options") as ask, \
                patch.object(widget, "_ask_card_payment", return_value=False), \
                patch(f"{_MOD}.route_tickets") as opd:
            widget._on_ticket_venta()
        # Un solo dialogo, dos tickets -> un solo clic en Imprimir.
        opd.assert_called_once()
        tickets = opd.call_args.args[2]
        self.assertEqual(len(tickets), 2)
        # Con descuento, la copia interna sigue siendo la de la empleada
        # (automática — solo se pregunta la forma de pago).
        self.assertIn("COPIA EMPLEADA", tickets[1])
        ask.assert_not_called()

    def test_store_copy_hides_customer_facing_data(self) -> None:
        widget = self._make_widget()
        widget._discount_active = False
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "Tel 123", "Calle 1")):
            customer = widget._build_venta_text()
            copy = widget._build_venta_text(store_copy=True)
        # La copia conserva formato: fecha/hora, articulos y total.
        self.assertIn("Fecha:", copy)
        self.assertIn("Pants", copy)
        self.assertIn("TOTAL A PAGAR:", copy)
        self.assertIn("COPIA TIENDA", copy)
        # Y oculta lo que ve el cliente.
        self.assertNotIn("MAXIMODA", copy)
        self.assertNotIn("Terminos y Condiciones", copy)
        self.assertNotIn("Gracias por su compra", copy)
        # El ticket del cliente no cambia.
        self.assertIn("MAXIMODA", customer)
        self.assertIn("Terminos y Condiciones", customer)
        self.assertIn("Gracias por su compra", customer)
        self.assertNotIn("COPIA TIENDA", customer)

    def test_terminal_commission_discounts_each_product_rounded(self) -> None:
        widget = self._make_widget()
        widget._discount_active = False
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")):
            copy = widget._build_venta_text(store_copy=True, terminal_commission=True)
        # 515.00 - 4.5% = 491.82 -> regla de redondeo (.82 > .69) -> 492.00
        self.assertIn("$492.00", copy)
        self.assertIn(tk_row("TOTAL A PAGAR:", "$492.00"), copy)
        self.assertNotIn("515.00", copy)

    def test_terminal_commission_on_employee_copy(self) -> None:
        widget = self._make_widget()
        widget._discount_active = True
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")):
            normal = widget._build_employee_copy_text()
            with_commission = widget._build_employee_copy_text(terminal_commission=True)
        # 515.00 - 5% empleada = 489.25; -4.5% terminal = 467.23 -> redondeo -> 467.50
        self.assertIn("$489.25", normal)
        self.assertIn("$467.50", with_commission)
        self.assertNotIn("$489.25", with_commission)

    def test_apartado_prints_two_copies_one_dialog(self) -> None:
        widget = self._make_widget()
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch(f"{_MOD}.QDialog.exec", return_value=QDialog.DialogCode.Accepted), \
                patch.object(QLineEdit, "text", return_value="Ana Lopez"), \
                patch(f"{_MOD}.route_tickets") as opd:
            widget._on_ticket_apartado()
        opd.assert_called_once()
        tickets = opd.call_args.args[2]
        self.assertEqual(len(tickets), 2)

    def test_empty_cart_does_not_open_dialog(self) -> None:
        widget = self._make_widget()
        widget._items = []
        with patch(f"{_MOD}.QMessageBox.information") as info, \
                patch(f"{_MOD}.route_tickets") as opd:
            widget._on_ticket_venta()
        opd.assert_not_called()
        info.assert_called_once()


class AskStoreCopyScanTests(unittest.TestCase):
    """El gafete de LA empleada en sesión equivale a 'sí, con copia'."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _make_widget(self) -> QuickSaleWidget:
        satellite = SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None)
        widget = QuickSaleWidget(satellite)
        widget._employee_code = "VEND-1"
        return widget

    def test_dialog_returns_copy_and_card_tuple(self) -> None:
        widget = self._make_widget()
        with patch.object(QDialog, "exec", self._fake_exec_scanning("EMPÑVEND-1")):
            self.assertEqual(widget._ask_venta_options(), (True, False))

    def test_scan_confirms_copy_only_for_session_employee(self) -> None:
        widget = self._make_widget()
        # Gafete propio, incluso con el mapeo del teclado español (Ñ por :)
        self.assertTrue(widget._scan_confirms_copy("EMP:VEND-1"))
        self.assertTrue(widget._scan_confirms_copy("EMPÑVEND-1"))
        # Gafete de OTRA empleada, un producto o vacío: no autorizan
        self.assertFalse(widget._scan_confirms_copy("EMP:VEND-2"))
        self.assertFalse(widget._scan_confirms_copy("SKU004838"))
        self.assertFalse(widget._scan_confirms_copy("   "))

    def _fake_exec_scanning(self, text: str):
        def _exec(dlg):
            field = dlg.findChildren(QLineEdit)[0]
            field.setText(text)
            field.returnPressed.emit()
            return 0

        return _exec

    def test_own_badge_scan_answers_yes(self) -> None:
        widget = self._make_widget()
        with patch.object(QDialog, "exec", self._fake_exec_scanning("EMPÑVEND-1")):
            wants_copy, _card = widget._ask_venta_options()
        self.assertTrue(wants_copy)

    def test_foreign_scan_does_not_answer(self) -> None:
        widget = self._make_widget()
        with patch.object(QDialog, "exec", self._fake_exec_scanning("EMP:VEND-2")):
            wants_copy, _card = widget._ask_venta_options()
        self.assertFalse(wants_copy)


class QuickSaleBusinessInfoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _make_widget(self, offline: bool) -> QuickSaleWidget:
        satellite = SimpleNamespace(offline_mode=offline, _kiosk_lookup_from_cache=None)
        return QuickSaleWidget(satellite)

    def test_offline_uses_cache_and_skips_db(self) -> None:
        widget = self._make_widget(offline=True)
        with patch(f"{_MOD}.load_business_info_cache",
                   return_value=("CACHED", "555", "Centro")) as load_cache, \
                patch(f"{_MOD}.get_session") as get_session:
            info = widget._load_business_info()
        self.assertEqual(info, ("CACHED", "555", "Centro"))
        get_session.assert_not_called()  # offline NO toca la DB (evita 5s)
        load_cache.assert_called_once()

    def test_offline_without_cache_falls_back_to_default(self) -> None:
        widget = self._make_widget(offline=True)
        with patch(f"{_MOD}.load_business_info_cache", return_value=None), \
                patch(f"{_MOD}.get_session") as get_session:
            info = widget._load_business_info()
        self.assertEqual(info, ("Uniformes", "", ""))
        get_session.assert_not_called()

    def test_memoizes_within_session(self) -> None:
        widget = self._make_widget(offline=True)
        with patch(f"{_MOD}.load_business_info_cache",
                   return_value=("X", "", "")) as load_cache:
            widget._load_business_info()
            widget._load_business_info()
        load_cache.assert_called_once()  # una sola carga aunque se pida 2 veces

    def test_online_reads_db_and_refreshes_cache(self) -> None:
        widget = self._make_widget(offline=False)
        config = SimpleNamespace(nombre_negocio="DBNAME", telefono="111", direccion="Av")
        with patch(f"{_MOD}.get_session") as get_session, \
                patch(f"{_MOD}.BusinessSettingsService.get_or_create", return_value=config), \
                patch(f"{_MOD}.save_business_info_cache") as save_cache:
            get_session.return_value.__enter__.return_value = MagicMock()
            info = widget._load_business_info()
        self.assertEqual(info, ("DBNAME", "111", "Av"))
        save_cache.assert_called_once_with("DBNAME", "111", "Av")


class LibretaCarritoTests(unittest.TestCase):
    """Al arrancar la impresión, el carrito se vacía en el mismo acto.

    El hueco real: imprimir 3 pzs, agregar una más al MISMO carrito y
    reimprimir anotaba 3 y luego 4 en la Libreta (7 pzs de 4 reales), y la
    siguiente clienta heredaba piezas ajenas."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _make_widget(self) -> QuickSaleWidget:
        satellite = SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None)
        widget = QuickSaleWidget(satellite)
        widget._employee_code = "VEND-1"
        widget._employee_name = "Daniel Fabian"
        widget._items = _items()
        return widget

    def _vender(self, widget: QuickSaleWidget, registros: list) -> None:
        """Corre el flujo de venta y simula que la impresión arrancó."""
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch.object(widget, "_ask_venta_options", return_value=(False, False)), \
                patch.object(widget, "_drenar_libreta_en_background"), \
                patch("pos_uniformes.services.libreta_local_queue_service.encolar_operacion",
                      side_effect=lambda op: registros.append(op)), \
                patch(f"{_MOD}.route_tickets") as route:
            widget._on_ticket_venta()
            route.assert_called_once()
            route.call_args.kwargs["on_printed"]()  # la impresión arrancó

    def test_imprimir_vacia_el_carrito_y_no_duplica_piezas(self) -> None:
        widget = self._make_widget()
        widget._discount_active = False
        registros: list = []

        self._vender(widget, registros)
        self.assertEqual(len(registros), 1)
        self.assertEqual(len(registros[0]["items"]), 1)  # anotó ANTES de vaciar
        self.assertEqual(widget._items, [])  # carrito vacío tras imprimir
        self.assertFalse(widget._discount_active)

        # "Cierra, añade otro producto y vuelve a imprimir": es una venta
        # nueva con SOLO la pieza nueva — ya no arrastra las anteriores.
        widget._items = [
            {"sku": "SKU000001", "nombre": "Playera", "talla": "8", "color": "",
             "precio": Decimal("120.00"), "cantidad": 1},
        ]
        self._vender(widget, registros)
        self.assertEqual(len(registros), 2)
        self.assertEqual(
            [it["sku"] for it in registros[1]["items"]], ["SKU000001"]
        )
        self.assertEqual(widget._items, [])

    def test_cerrar_sin_imprimir_conserva_el_carrito(self) -> None:
        # Si NO se imprime (on_printed nunca dispara), el carrito sigue ahí:
        # cancelar la impresión no le borra la captura a la empleada.
        widget = self._make_widget()
        widget._discount_active = False
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch.object(widget, "_ask_venta_options", return_value=(False, False)), \
                patch(f"{_MOD}.route_tickets"):
            widget._on_ticket_venta()
        self.assertEqual(len(widget._items), 1)


if __name__ == "__main__":
    unittest.main()


class BotonesCarritoTests(unittest.TestCase):
    """Cada renglón del carrito trae − / + / 🗑 (táctil): restar quita 1,
    sumar agrega 1 y el bote elimina la línea completa."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _widget(self):
        satellite = SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None)
        w = QuickSaleWidget(satellite)
        w._employee_code = "VEND-2"
        w._items = [
            {"sku": "S1", "nombre": "Chamarra", "talla": "2", "color": "",
             "precio": Decimal("175.00"), "cantidad": 2},
            {"sku": "S2", "nombre": "Playera", "talla": "10", "color": "",
             "precio": Decimal("145.00"), "cantidad": 1},
        ]
        w._refresh_items_table()
        return w

    def test_sumar_restar_y_eliminar_linea(self) -> None:
        w = self._widget()
        w._on_add_one(0)
        self.assertEqual(w._items[0]["cantidad"], 3)
        w._on_remove(0)
        self.assertEqual(w._items[0]["cantidad"], 2)
        w._on_delete_line(0)  # elimina la línea aunque tenga 2 piezas
        self.assertEqual(len(w._items), 1)
        self.assertEqual(w._items[0]["sku"], "S2")

    def test_cada_renglon_trae_sus_tres_botones(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        w = self._widget()
        acciones = w._items_table.cellWidget(0, 4)
        botones = acciones.findChildren(QPushButton)
        self.assertEqual(len(botones), 3)
        self.assertEqual({b.text() for b in botones}, {"−", "+", "🗑"})
