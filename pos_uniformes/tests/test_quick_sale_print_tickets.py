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

    def test_venta_no_discount_prints_one_ticket(self) -> None:
        widget = self._make_widget()
        widget._discount_active = False
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch(f"{_MOD}.open_tickets_print_dialog") as opd:
            widget._on_ticket_venta()
        opd.assert_called_once()
        tickets = opd.call_args.args[2]
        self.assertEqual(len(tickets), 1)

    def test_venta_with_discount_prints_two_tickets_one_dialog(self) -> None:
        widget = self._make_widget()
        widget._discount_active = True
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch(f"{_MOD}.open_tickets_print_dialog") as opd:
            widget._on_ticket_venta()
        # Un solo dialogo, dos tickets -> un solo clic en Imprimir.
        opd.assert_called_once()
        tickets = opd.call_args.args[2]
        self.assertEqual(len(tickets), 2)

    def test_apartado_prints_two_copies_one_dialog(self) -> None:
        widget = self._make_widget()
        with patch.object(widget, "_load_business_info", return_value=("MAXIMODA", "", "")), \
                patch(f"{_MOD}.QDialog.exec", return_value=QDialog.DialogCode.Accepted), \
                patch.object(QLineEdit, "text", return_value="Ana Lopez"), \
                patch(f"{_MOD}.open_tickets_print_dialog") as opd:
            widget._on_ticket_apartado()
        opd.assert_called_once()
        tickets = opd.call_args.args[2]
        self.assertEqual(len(tickets), 2)

    def test_empty_cart_does_not_open_dialog(self) -> None:
        widget = self._make_widget()
        widget._items = []
        with patch(f"{_MOD}.QMessageBox.information") as info, \
                patch(f"{_MOD}.open_tickets_print_dialog") as opd:
            widget._on_ticket_venta()
        opd.assert_not_called()
        info.assert_called_once()


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
