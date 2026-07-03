"""Tests de los guards de modo offline en la ventana satélite.

Bug original: _handle_quote_filters_changed y _handle_quick_scan llamaban
get_session() sin checar offline_mode — la UI se congelaba el connect_timeout
completo (~5s) en cada acción y luego mostraba un error confuso.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _fail_if_called(*_args, **_kwargs):
    raise AssertionError("get_session() no debe llamarse en modo offline")


class OfflineGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _make_offline_window(self):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        window = QuoteSatelliteWindow(user_id=1)
        window.offline_mode = True
        return window

    def test_quote_filters_changed_offline_refreshes_local_list_without_db(self) -> None:
        window = self._make_offline_window()
        window._refresh_offline_quotes = Mock()
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session",
            side_effect=_fail_if_called,
        ):
            window._handle_quote_filters_changed()
        window._refresh_offline_quotes.assert_called_once()

    def test_quick_scan_offline_adds_sku_without_db(self) -> None:
        window = self._make_offline_window()
        window.quick_scan_input.setText("SKU000123")
        window._add_quote_item_by_sku = Mock()
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session",
            side_effect=_fail_if_called,
        ):
            window._handle_quick_scan()
        window._add_quote_item_by_sku.assert_called_once_with("SKU000123", 1)
        self.assertEqual(window.quick_scan_input.text(), "")

    def test_quick_scan_online_still_uses_db_lookup(self) -> None:
        window = self._make_offline_window()
        window.offline_mode = False
        window.quick_scan_input.setText("SKU000123")
        session_mock = Mock()
        get_session_cm = Mock()
        get_session_cm.__enter__ = Mock(return_value=session_mock)
        get_session_cm.__exit__ = Mock(return_value=False)
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session",
            return_value=get_session_cm,
        ) as get_session_mock, patch(
            "pos_uniformes.ui.quote_satellite_window.find_active_sale_client_by_code",
            return_value=None,
        ):
            window._add_quote_item_by_sku = Mock()
            window._handle_quick_scan()
        get_session_mock.assert_called_once()
        window._add_quote_item_by_sku.assert_called_once_with("SKU000123", 1)


if __name__ == "__main__":
    unittest.main()
