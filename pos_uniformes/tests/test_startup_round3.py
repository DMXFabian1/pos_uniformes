"""Ronda 3: arranque del satélite desde cache, Bodega sin N+1 y diferida,
QWebEngineView perezoso y refresh_all más barata por dentro."""

from __future__ import annotations

import inspect
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("POS_UNIFORMES_DB_HOST", "localhost")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

from pos_uniformes.services.bodega_service import BodegaService
from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

_QSW = "pos_uniformes.ui.quote_satellite_window"


class SatelliteCacheFirstStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_load_catalog_from_disk_cache_success(self) -> None:
        fake = SimpleNamespace(
            catalog_snapshot_rows=[],
            _catalog_snapshot_loaded_once=False,
            _rebuild_sku_index=MagicMock(),
            _rebuild_catalog_level_combo=MagicMock(),
            _update_meilisearch_status=MagicMock(),
        )
        rows = [{"sku": "SKU-1"}]
        with patch(f"{_QSW}.load_catalog_cache", return_value=rows):
            ok = QuoteSatelliteWindow._load_catalog_from_disk_cache(fake)
        self.assertTrue(ok)
        self.assertEqual(fake.catalog_snapshot_rows, rows)
        fake._rebuild_sku_index.assert_called_once()
        fake._rebuild_catalog_level_combo.assert_called_once()
        # Un refresh manual posterior sí debe re-indexar en background.
        self.assertTrue(fake._catalog_snapshot_loaded_once)

    def test_load_catalog_from_disk_cache_empty_falls_back(self) -> None:
        fake = SimpleNamespace(_rebuild_sku_index=MagicMock())
        with patch(f"{_QSW}.load_catalog_cache", return_value=[]):
            self.assertFalse(QuoteSatelliteWindow._load_catalog_from_disk_cache(fake))
        fake._rebuild_sku_index.assert_not_called()

    def _fake_online_window(self, cache_ok: bool) -> SimpleNamespace:
        return SimpleNamespace(
            offline_mode=False,
            _load_catalog_from_disk_cache=MagicMock(return_value=cache_ok),
            _refresh_client_combo=MagicMock(),
            _refresh_catalog_snapshot=MagicMock(),
            _refresh_quotes=MagicMock(),
            _refresh_tariff_schools=MagicMock(),
            _refresh_catalog_browser=MagicMock(),
            _refresh_guided_browser=MagicMock(),
            _refresh_quote_cart_table=MagicMock(),
            _refresh_recent_lookup_table=MagicMock(),
            _start_background_db_refresh=MagicMock(),
            _set_status=MagicMock(),
        )

    def _run_refresh_all(self, fake, **kwargs) -> None:
        ctx = MagicMock()
        ctx.__enter__.return_value = MagicMock()
        with patch(f"{_QSW}.get_session", return_value=ctx):
            QuoteSatelliteWindow.refresh_all(fake, **kwargs)

    def test_startup_uses_cache_and_background_refresh(self) -> None:
        fake = self._fake_online_window(cache_ok=True)
        self._run_refresh_all(fake, catalog_from_cache=True)
        # El catálogo NO se trae de la base en el hilo de UI...
        fake._refresh_catalog_snapshot.assert_not_called()
        # ...el watchdog en background trae el fresco.
        fake._start_background_db_refresh.assert_called_once()

    def test_startup_without_cache_falls_back_to_db(self) -> None:
        fake = self._fake_online_window(cache_ok=False)
        self._run_refresh_all(fake, catalog_from_cache=True)
        fake._refresh_catalog_snapshot.assert_called_once()
        fake._start_background_db_refresh.assert_not_called()

    def test_manual_refresh_keeps_sync_catalog(self) -> None:
        fake = self._fake_online_window(cache_ok=True)
        self._run_refresh_all(fake)
        fake._load_catalog_from_disk_cache.assert_not_called()
        fake._refresh_catalog_snapshot.assert_called_once()


class BodegaBatchDesgloseTests(unittest.TestCase):
    def _contenido(self, caja_id, prod_id, nombre, talla, cantidad, variante_id):
        return SimpleNamespace(
            caja_id=caja_id,
            cantidad=cantidad,
            variante_id=variante_id,
            variante=SimpleNamespace(
                talla=talla,
                color="",
                producto=SimpleNamespace(id=prod_id, nombre=nombre),
            ),
        )

    def test_groups_by_caja_in_single_query(self) -> None:
        session = MagicMock()
        session.scalars.return_value.unique.return_value.all.return_value = [
            self._contenido(1, 10, "Pants", "6", 3, 100),
            self._contenido(1, 10, "Pants", "8", 2, 101),
            self._contenido(2, 20, "Playera", "M", 5, 200),
        ]
        result = BodegaService.desglose_contenido_cajas(session, [1, 2, 3])
        session.scalars.assert_called_once()
        self.assertEqual(result[1][0]["producto"], "Pants")
        self.assertEqual(result[1][0]["total"], 5)
        self.assertEqual(result[2][0]["total"], 5)
        self.assertEqual(result[3], [])  # caja vacía presente con lista vacía

    def test_empty_ids_skip_query(self) -> None:
        session = MagicMock()
        self.assertEqual(BodegaService.desglose_contenido_cajas(session, []), {})
        session.scalars.assert_not_called()


class BodegaDeferredLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_cajas_load_on_first_show_only(self) -> None:
        from pos_uniformes.ui.views.bodega_view import BodegaWidget

        class _Probe(BodegaWidget):
            def __init__(self) -> None:  # sin el __init__ real (usa DB)
                QWidget.__init__(self)
                self._cajas_loaded = False
                self.refresh_calls = 0

            def _refresh_cajas(self) -> None:
                self._cajas_loaded = True
                self.refresh_calls += 1

        probe = _Probe()
        self.assertEqual(probe.refresh_calls, 0)  # el __init__ ya no carga
        probe.show()
        self.assertEqual(probe.refresh_calls, 1)
        probe.hide()
        probe.show()
        self.assertEqual(probe.refresh_calls, 1)  # solo la primera vez
        probe.deleteLater()

    def test_real_init_defers_refresh(self) -> None:
        from pos_uniformes.ui.views.bodega_view import BodegaWidget

        source = inspect.getsource(BodegaWidget.__init__)
        self.assertNotIn("self._refresh_cajas()", source)


class PanelLazyWebViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_constructor_does_not_start_chromium(self) -> None:
        from pos_uniformes.ui.views.panel_uniformes_view import PanelUniformesWidget

        widget = PanelUniformesWidget(window=SimpleNamespace())
        self.assertIsNone(widget._web_view)
        self.assertFalse(widget._web_view_attempted)
        widget.deleteLater()

    def test_show_event_creates_web_view(self) -> None:
        from pos_uniformes.ui.views.panel_uniformes_view import PanelUniformesWidget

        widget = PanelUniformesWidget(window=SimpleNamespace())
        with patch.object(widget, "_ensure_web_view") as ensure:
            widget.show()
        ensure.assert_called()
        widget.deleteLater()


class RefreshAllInternalsTests(unittest.TestCase):
    def test_refresh_summary_uses_single_round_trip(self) -> None:
        from pos_uniformes.ui.main_window import MainWindow

        source = inspect.getsource(MainWindow._refresh_summary)
        self.assertNotIn("session.scalar(", source)
        self.assertEqual(source.count("session.execute("), 1)

    def test_refresh_combos_hydrates_variants_once(self) -> None:
        from pos_uniformes.ui.main_window import MainWindow

        source = inspect.getsource(MainWindow._refresh_combos)
        # Una sola query de variantes; las activas se derivan en memoria.
        self.assertIn("variantes_activas = [v for v in variantes_inventario", source)
        # selectinload, no joinedload: el JOIN repetiría las columnas de
        # Producto en cada una de las ~4,800 filas por la red.
        self.assertIn("selectinload(Variante.producto)", source)


if __name__ == "__main__":
    unittest.main()
