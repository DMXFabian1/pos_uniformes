"""Regresiones de los fixes de arranque/congelamiento.

1. El refresh completo corre UNA vez (en MainWindow.__init__); main.py no
   lo repite. Antes corría dos veces.
2. (2026-11-12) _run_operational_checks se retiró junto con el recordatorio
   de corte de las 5: el POS ya no lleva sesión de caja (el corte vive en el
   kiosko). Daniel: «no lo necesito, retira también movimientos y el corte».
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


class SingleStartupRefreshTests(unittest.TestCase):
    """__init__ hace el refresh completo UNA vez; main.py no la repite."""

    def test_main_window_init_keeps_full_refresh(self) -> None:
        # Quitarla de __init__ deja los cachés vacíos y cualquier señal de
        # filtro dispara queries lazy (y con DB caída, aborta el proceso).
        source = inspect.getsource(MainWindow.__init__)
        self.assertIn("self.refresh_all()", source)

    def test_launch_flow_no_repite_refresh_ni_abre_caja(self) -> None:
        import pos_uniformes.main as main_module

        source = inspect.getsource(main_module.main)
        self.assertNotIn(
            "startup_window.refresh_all()",
            source,
            "main.py volvió a llamar refresh_all completa: duplica las ~45 "
            "queries del arranque.",
        )
        # 2026-11-12: sin sesión de caja en el POS, el arranque ya no la pide.
        self.assertNotIn("ensure_cash_session", source)
        self.assertNotIn("refresh_after_cash_session", source)


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
