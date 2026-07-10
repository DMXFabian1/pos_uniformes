"""Watchdog de reconexión del satélite.

Reportado en piso (2026-07-08): apagar la PC principal con el satélite ya
encendido lo tumbaba; encenderla después no se notaba (precios viejos hasta
reiniciar). El modo se fija al arrancar, pero la conectividad cambia — el
watchdog refresca el catálogo cuando la DB está disponible y degrada sin
cerrar cuando no lo está.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow


class ThreadingExcepthookTests(unittest.TestCase):
    def test_install_sets_both_sys_and_threading_excepthook(self) -> None:
        import sys
        import threading
        import tempfile
        from pathlib import Path

        from pos_uniformes.utils.satellite_excepthook import install_gui_excepthook

        orig_sys, orig_thread = sys.excepthook, threading.excepthook
        try:
            with tempfile.TemporaryDirectory() as tmp:
                install_gui_excepthook(Path(tmp) / "errors.log")
                self.assertIsNot(sys.excepthook, orig_sys)
                self.assertIsNot(threading.excepthook, orig_thread)
        finally:
            sys.excepthook, threading.excepthook = orig_sys, orig_thread


class ReconnectWatchdogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _window(self) -> QuoteSatelliteWindow:
        return QuoteSatelliteWindow(user_id=1)

    def test_fresh_rows_replace_catalog_and_hide_banner(self) -> None:
        window = self._window()
        window.offline_mode = False
        new_rows = [{"sku": "SKU-NEW", "producto_nombre_base": "Nuevo"}]
        with patch(
            "pos_uniformes.ui.quote_satellite_window.save_catalog_cache"
        ) as save_cache:
            window._on_db_refresh_ready(new_rows, None)
        self.assertEqual(window.catalog_snapshot_rows, new_rows)
        self.assertEqual(window._find_row_by_sku("SKU-NEW")["producto_nombre_base"], "Nuevo")
        save_cache.assert_called_once_with(new_rows)
        self.assertTrue(window.offline_banner.isHidden())

    def test_db_down_keeps_cache_and_shows_offline_banner(self) -> None:
        window = self._window()
        window.catalog_snapshot_rows = [{"sku": "SKU-OLD"}]
        window._on_db_refresh_ready(None, None)  # DB no disponible
        # No se pierde el catálogo, no se cierra nada, banner de sin conexión.
        self.assertEqual(window.catalog_snapshot_rows, [{"sku": "SKU-OLD"}])
        self.assertFalse(window.offline_banner.isHidden())
        self.assertIn("Sin conexion", window.offline_banner.text())

    def test_offline_boot_picks_up_db_when_pc_turns_on(self) -> None:
        # Arrancó offline; el watchdog encuentra la DB y trae datos frescos.
        window = self._window()
        window.offline_mode = True
        rows = [{"sku": "SKU-LIVE"}]
        with patch("pos_uniformes.ui.quote_satellite_window.save_catalog_cache"):
            window._on_db_refresh_ready(rows, None)
        self.assertEqual(window.catalog_snapshot_rows, rows)
        self.assertIn("actualizado", window.offline_banner.text().lower())

    def test_worker_emits_none_when_probe_fails(self) -> None:
        window = self._window()
        window._db_refresh_ready = Mock()
        with patch(
            "pos_uniformes.services.satellite_startup_service.probe_database_host",
            return_value=False,
        ):
            import threading
            with patch.object(threading, "Thread") as thread_cls:
                window._start_background_db_refresh()
                # ejecuta el target sincrónicamente para verificar el emit
                target = thread_cls.call_args.kwargs["target"]
                target()
        window._db_refresh_ready.emit.assert_called_once_with(None, None)


if __name__ == "__main__":
    unittest.main()
