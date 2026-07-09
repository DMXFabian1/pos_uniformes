"""Resiliencia del satélite ante caídas de conexión con la PC principal.

Reportado en piso (2026-07-08): "(psycopg.OperationalError) server closed the
connection unexpectedly" mostrado como traceback crudo al escanear un SKU. La
LAN por Wi-Fi parpadea; la consulta debe caer al catálogo local y mostrar un
mensaje amigable en vez del traceback.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from sqlalchemy.exc import OperationalError

from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow


def _db_down(*_a, **_k):
    raise OperationalError("SELECT ...", {}, Exception("server closed the connection"))


class EnginePoolConfigTests(unittest.TestCase):
    def test_engine_has_pre_ping_and_recycle(self) -> None:
        from pos_uniformes.database.connection import engine

        # pool_pre_ping se refleja en el pool como _pre_ping True.
        self.assertTrue(getattr(engine.pool, "_pre_ping", False))
        self.assertEqual(engine.pool._recycle, 1800)


class KioskLookupFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _online_window(self) -> QuoteSatelliteWindow:
        window = QuoteSatelliteWindow(user_id=1)
        window.offline_mode = False
        window.catalog_snapshot_rows = [
            {
                "sku": "SKU004201", "producto_nombre_base": "Pants 2pz", "escuela_nombre": "General",
                "tipo_prenda_nombre": "Pant", "tipo_pieza_nombre": "Pants 2pz", "talla": "6",
                "color": "Azul", "precio_venta": "450.00", "stock_actual": 3,
                "producto_activo": True, "variante_activo": True,
            }
        ]
        return window

    def test_lookup_falls_back_to_cache_on_db_error(self) -> None:
        window = self._online_window()
        window.kiosk_scan_input.setText("SKU004201")
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session", side_effect=_db_down
        ), patch(
            "pos_uniformes.ui.quote_satellite_window.QMessageBox.warning"
        ) as warn:
            window._handle_lookup_scan()
        # Encontró el precio local — sin popup de error, con snapshot cargado.
        self.assertIsNotNone(window.lookup_snapshot)
        self.assertEqual(window.lookup_snapshot.sku, "SKU004201")
        warn.assert_not_called()

    def test_lookup_no_ugly_traceback_when_cache_also_misses(self) -> None:
        window = self._online_window()
        window.catalog_snapshot_rows = []  # ni en cache
        window.kiosk_scan_input.setText("SKU999999")
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session", side_effect=_db_down
        ), patch(
            "pos_uniformes.ui.quote_satellite_window.QMessageBox.warning"
        ) as warn:
            window._handle_lookup_scan()
        self.assertIsNone(window.lookup_snapshot)
        warn.assert_called_once()
        msg = warn.call_args.args[2]
        # Lo esencial: NUNCA el traceback de psycopg en pantalla.
        self.assertNotIn("psycopg", msg)
        self.assertNotIn("Traceback", msg)
        self.assertNotIn("OperationalError", msg)

    def test_lookup_shows_friendly_message_when_db_down_and_no_cache_loaded(self) -> None:
        # Si _kiosk_lookup_from_cache lanza un error de DB (no ValueError),
        # se muestra el mensaje de "sin conexión".
        window = self._online_window()
        window.kiosk_scan_input.setText("SKU004201")
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session", side_effect=_db_down
        ), patch.object(
            window, "_kiosk_lookup_from_cache", side_effect=_db_down
        ), patch(
            "pos_uniformes.ui.quote_satellite_window.QMessageBox.warning"
        ) as warn:
            window._handle_lookup_scan()
        self.assertIsNone(window.lookup_snapshot)
        msg = warn.call_args.args[2]
        self.assertIn("Sin conexion con la PC principal", msg)
        self.assertNotIn("psycopg", msg)

    def test_add_item_falls_back_to_cache_on_db_error(self) -> None:
        window = self._online_window()
        window._can_build_cart = lambda: True
        window._add_quote_item_from_cache = Mock()
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session", side_effect=_db_down
        ):
            window._add_quote_item_by_sku("SKU004201", 1)
        window._add_quote_item_from_cache.assert_called_once_with("SKU004201", 1)


if __name__ == "__main__":
    unittest.main()
