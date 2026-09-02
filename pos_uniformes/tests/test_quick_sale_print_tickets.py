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
                patch.object(widget, "_ask_store_copy", return_value=False), \
                patch(f"{_MOD}.route_tickets") as opd:
            widget._on_ticket_venta()
        opd.assert_called_once()
        tickets = opd.call_args.args[2]
        self.assertEqual(len(tickets), 1)
        # Sin copia tampoco hay checkbox de comisión (no habría a qué aplicarlo).
        self.assertIsNone(opd.call_args.kwargs["alt_tickets"])
        self.assertIsNone(opd.call_args.kwargs["alt_checkbox_label"])

    def test_venta_with_copy_confirmed_prints_store_copy(self) -> None:
        widget = self._make_widget()
        widget._discount_active = False
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch.object(widget, "_ask_store_copy", return_value=True), \
                patch(f"{_MOD}.route_tickets") as opd:
            widget._on_ticket_venta()
        opd.assert_called_once()
        tickets = opd.call_args.args[2]
        self.assertEqual(len(tickets), 2)
        self.assertIn("COPIA TIENDA", tickets[1])

    def test_venta_with_discount_prints_two_tickets_one_dialog(self) -> None:
        widget = self._make_widget()
        widget._discount_active = True
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch.object(widget, "_ask_store_copy") as ask, \
                patch(f"{_MOD}.route_tickets") as opd:
            widget._on_ticket_venta()
        # Un solo dialogo, dos tickets -> un solo clic en Imprimir.
        opd.assert_called_once()
        tickets = opd.call_args.args[2]
        self.assertEqual(len(tickets), 2)
        # Con descuento, la copia interna sigue siendo la de la empleada
        # (automática — no se pregunta).
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
        # 515.00 - 6% = 484.10 -> regla de redondeo (.10 <= .19) -> 484.00
        self.assertIn("$484.00", copy)
        self.assertIn(tk_row("TOTAL A PAGAR:", "$484.00"), copy)
        self.assertNotIn("515.00", copy)

    def test_terminal_commission_on_employee_copy(self) -> None:
        widget = self._make_widget()
        widget._discount_active = True
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")):
            normal = widget._build_employee_copy_text()
            with_commission = widget._build_employee_copy_text(terminal_commission=True)
        # 515.00 - 5% empleada = 489.25; -6% terminal = 459.90 -> redondeo -> 460.00
        self.assertIn("$489.25", normal)
        self.assertIn("$460.00", with_commission)
        self.assertNotIn("$489.25", with_commission)

    def test_on_ticket_venta_passes_commission_alternative(self) -> None:
        widget = self._make_widget()
        widget._discount_active = False
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch.object(widget, "_ask_store_copy", return_value=True), \
                patch(f"{_MOD}.route_tickets") as opd:
            widget._on_ticket_venta()
        kwargs = opd.call_args.kwargs
        tickets = opd.call_args.args[2]
        self.assertIn("6%", kwargs["alt_checkbox_label"])
        # El del cliente es identico en ambos juegos; solo cambia la copia.
        self.assertEqual(kwargs["alt_tickets"][0], tickets[0])
        self.assertIn("COPIA TIENDA", kwargs["alt_tickets"][1])
        self.assertIn("$484.00", kwargs["alt_tickets"][1])

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
            self.assertTrue(widget._ask_store_copy())

    def test_foreign_scan_does_not_answer(self) -> None:
        widget = self._make_widget()
        with patch.object(QDialog, "exec", self._fake_exec_scanning("EMP:VEND-2")):
            self.assertFalse(widget._ask_store_copy())


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


if __name__ == "__main__":
    unittest.main()
