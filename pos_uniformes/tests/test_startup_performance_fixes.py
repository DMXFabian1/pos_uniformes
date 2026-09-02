"""Regresiones de los 3 fixes de arranque/congelamiento.

1. MainWindow.__init__ NO llama refresh_all (el flujo de main.py la llama
   una sola vez, después de ensure_cash_session). Antes corría dos veces.
2. _run_operational_checks hace probe TCP antes de tocar SQLAlchemy (sin
   probe, congelaba la app cada 60s con la base caída).
3. _refresh_catalog_snapshot del satélite ya no indexa Meilisearch síncrono
   en el hilo de UI: el arranque lo hace en background y los refresh
   posteriores usan notify_catalog_changed (también background).
"""

from __future__ import annotations

import inspect
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("POS_UNIFORMES_DB_HOST", "localhost")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.main_window import MainWindow
from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

_MW = "pos_uniformes.ui.main_window"


class SingleStartupRefreshTests(unittest.TestCase):
    """__init__ hace el refresh completo UNA vez; el flujo de login solo
    repinta lo de caja. Antes main.py repetía refresh_all completa."""

    def test_main_window_init_keeps_full_refresh(self) -> None:
        # Quitarla de __init__ deja los cachés vacíos y cualquier señal de
        # filtro dispara queries lazy (y con DB caída, aborta el proceso).
        source = inspect.getsource(MainWindow.__init__)
        self.assertIn("self.refresh_all()", source)

    def test_launch_flow_uses_targeted_cash_refresh(self) -> None:
        import pos_uniformes.main as main_module

        source = inspect.getsource(main_module.main)
        self.assertNotIn(
            "startup_window.refresh_all()",
            source,
            "main.py volvió a llamar refresh_all completa: duplica las ~45 "
            "queries del arranque (usa refresh_after_cash_session).",
        )
        self.assertIn("refresh_after_cash_session()", source)

    def test_targeted_refresh_only_touches_cash_views(self) -> None:
        fake = SimpleNamespace(
            _refresh_cash_session=MagicMock(),
            _refresh_summary=MagicMock(),
            _refresh_permissions=MagicMock(),
            _refresh_catalog=MagicMock(),
            _invalidate_listing_snapshot_caches=MagicMock(),
            status_label=MagicMock(),
        )
        session = MagicMock()
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        with patch(f"{_MW}.get_session", return_value=ctx):
            MainWindow.refresh_after_cash_session(fake)
        fake._refresh_cash_session.assert_called_once_with(session)
        fake._refresh_summary.assert_called_once_with(session)
        fake._refresh_permissions.assert_called_once()
        fake._refresh_catalog.assert_not_called()


class DetectDbModeSettingsTests(unittest.TestCase):
    """La detección de host debe RECONSTRUIR el singleton settings.

    Importar config dentro de _detect_db_mode congela settings con el host
    previo; sin el rebind, la app diría 'Tienda' pero el engine conectaría a
    localhost (ventas en la base equivocada)."""

    def test_detected_host_lands_in_settings(self) -> None:
        import pos_uniformes.main as main_module
        import pos_uniformes.utils.config as config

        old_settings = config.settings
        old_env = os.environ.get("POS_UNIFORMES_DB_HOST")
        try:
            os.environ.pop("POS_UNIFORMES_DB_HOST", None)
            with patch(
                "pos_uniformes.utils.config.load_runtime_env_overrides",
                return_value={"POS_UNIFORMES_SERVER_HOST": "10.9.9.9"},
            ), patch.object(main_module._socket, "create_connection") as conn:
                conn.return_value = MagicMock()
                mode = main_module._detect_db_mode()
            self.assertEqual(mode, "windows")
            self.assertEqual(
                config.settings.db_host,
                "10.9.9.9",
                "settings quedó congelado con el host previo a la detección",
            )
        finally:
            config.settings = old_settings
            if old_env is None:
                os.environ.pop("POS_UNIFORMES_DB_HOST", None)
            else:
                os.environ["POS_UNIFORMES_DB_HOST"] = old_env


class OperationalChecksProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _fake_window(self) -> SimpleNamespace:
        return SimpleNamespace(
            active_cash_session_id=1,
            cash_session_requires_cut=False,
            cash_session_cut_reminder_key=None,
        )

    def test_skips_db_when_host_unreachable(self) -> None:
        fake = self._fake_window()
        with patch(
            "pos_uniformes.services.satellite_startup_service.probe_database_host",
            return_value=False,
        ), patch(f"{_MW}.get_session") as get_session:
            MainWindow._run_operational_checks(fake)
        get_session.assert_not_called()

    def test_queries_db_when_host_responds(self) -> None:
        fake = self._fake_window()
        session = MagicMock()
        session.get.return_value = None  # sesión de caja no encontrada: sale limpio
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        with patch(
            "pos_uniformes.services.satellite_startup_service.probe_database_host",
            return_value=True,
        ), patch(f"{_MW}.get_session", return_value=ctx) as get_session:
            MainWindow._run_operational_checks(fake)
        get_session.assert_called_once()


class SatelliteCatalogRefreshIndexingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _fake_satellite(self) -> SimpleNamespace:
        return SimpleNamespace(
            catalog_snapshot_rows=[],
            _catalog_snapshot_loaded_once=False,
            _rebuild_sku_index=MagicMock(),
            _rebuild_catalog_level_combo=MagicMock(),
            _update_meilisearch_status=MagicMock(),
        )

    def _run_refresh(self, fake) -> MagicMock:
        mod = "pos_uniformes.ui.quote_satellite_window"
        with patch(f"{mod}.load_catalog_snapshot_rows", return_value=[]), \
                patch(f"{mod}.save_catalog_cache"), \
                patch(f"{mod}.list_all_active_links", return_value=[]), \
                patch(f"{mod}.save_school_links_cache"), \
                patch(
                    "pos_uniformes.services.meilisearch_service.notify_catalog_changed"
                ) as notify:
            QuoteSatelliteWindow._refresh_catalog_snapshot(fake, session=object())
        return notify

    def test_first_refresh_does_not_reindex(self) -> None:
        # El arranque ya lanzó autostart_and_reindex en background; el primer
        # refresh no debe duplicar el trabajo ni bloquear.
        fake = self._fake_satellite()
        notify = self._run_refresh(fake)
        notify.assert_not_called()
        self.assertTrue(fake._catalog_snapshot_loaded_once)

    def test_later_refreshes_reindex_in_background(self) -> None:
        fake = self._fake_satellite()
        fake._catalog_snapshot_loaded_once = True
        notify = self._run_refresh(fake)
        notify.assert_called_once()

    def test_sync_indexing_method_is_gone(self) -> None:
        self.assertFalse(
            hasattr(QuoteSatelliteWindow, "_try_index_meilisearch"),
            "Volvió el indexado síncrono de Meilisearch en el hilo de UI.",
        )


if __name__ == "__main__":
    unittest.main()
