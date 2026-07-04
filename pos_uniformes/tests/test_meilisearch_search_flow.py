"""Tests del flujo de búsqueda con Meilisearch.

Bug original: los consumidores re-filtraban los hits de Meilisearch con un
"todas las palabras como substring" — eso mataba la tolerancia a typos y los
sinónimos ("camisa balnca" → 0 resultados aunque Meilisearch la encontraba).
El fix: matchingStrategy=all en el motor (exige todas las palabras CON typos
y sinónimos) y el filtro local de texto solo corre como fallback sin Meili.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class IndexSettingsTests(unittest.TestCase):
    def test_genero_is_searchable(self) -> None:
        from pos_uniformes.services.meilisearch_service import index_settings

        self.assertIn("genero", index_settings()["searchableAttributes"])

    def test_level_gender_and_color_synonyms_present(self) -> None:
        from pos_uniformes.services.meilisearch_service import index_settings

        synonyms = index_settings()["synonyms"]
        self.assertIn("secundaria", synonyms["sec"])
        self.assertIn("primaria", synonyms["prim"])
        self.assertIn("preescolar", synonyms["kinder"])
        self.assertIn("mujer", synonyms["niña"])
        self.assertIn("hombre", synonyms["niño"])
        self.assertIn("azul marino", synonyms["marino"])
        self.assertIn("moño", synonyms["corbatin"])

    def test_typo_tolerance_still_disabled_on_sku(self) -> None:
        from pos_uniformes.services.meilisearch_service import index_settings

        self.assertIn("sku", index_settings()["typoTolerance"]["disableOnAttributes"])


class EnsureRunningTests(unittest.TestCase):
    """Auto-arranque silencioso: sin binario instalado NO descarga nada."""

    def test_returns_true_if_already_running(self) -> None:
        from pos_uniformes.services import meilisearch_service

        with patch.object(meilisearch_service, "is_available", return_value=True):
            self.assertTrue(meilisearch_service.ensure_running())

    def test_missing_binary_returns_false_without_downloading(self) -> None:
        from pos_uniformes.services import meilisearch_service

        with patch.object(meilisearch_service, "is_available", return_value=False), patch.object(
            meilisearch_service, "_start_binary"
        ) as start:
            result = meilisearch_service.ensure_running(install_dir="/ruta/inexistente")
        self.assertFalse(result)
        start.assert_not_called()

    def test_starts_binary_when_installed(self) -> None:
        import tempfile
        from pathlib import Path

        from pos_uniformes.services import meilisearch_service

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "meilisearch.exe").write_bytes(b"")
            with patch.object(meilisearch_service, "is_available", return_value=False), patch.object(
                meilisearch_service, "_start_binary", return_value=True
            ) as start:
                result = meilisearch_service.ensure_running(install_dir=tmp)
            self.assertTrue(result)
            start.assert_called_once()


class SearchUsesMatchingStrategyAllTests(unittest.TestCase):
    def test_search_requests_all_words_matching(self) -> None:
        from pos_uniformes.services import meilisearch_service

        fake_index = Mock()
        fake_index.search.return_value = {"hits": [{"sku": "SKU-1"}]}
        with patch.object(meilisearch_service, "_get_index", return_value=fake_index):
            hits = meilisearch_service.search("camisa blanca")
        self.assertEqual(hits, [{"sku": "SKU-1"}])
        _query, opts = fake_index.search.call_args.args
        self.assertEqual(opts.get("matchingStrategy"), "all")


def _catalog_row(sku: str, nombre: str, color: str = "Blanco") -> dict:
    return {
        "sku": sku,
        "producto_nombre_base": nombre,
        "talla": "6",
        "color": color,
        "escuela_nombre": "General",
        "tipo_prenda_nombre": "",
        "tipo_pieza_nombre": "Camisa",
        "producto_activo": True,
        "variante_activo": True,
        "precio_venta": "100.00",
    }


class QuickSearchTypoSurvivalTests(unittest.TestCase):
    """El resultado de Meilisearch con typo NO debe morir en el filtro local."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _make_dialog(self, rows: list[dict]):
        from pos_uniformes.ui.dialogs.quick_product_search_dialog import QuickProductSearchDialog

        return QuickProductSearchDialog(catalog_rows=rows)

    def test_typo_query_keeps_meilisearch_hit(self) -> None:
        rows = [
            _catalog_row("SKU-1", "Camisa Blanca"),
            _catalog_row("SKU-2", "Pants Rojo", color="Rojo"),
        ]
        dialog = self._make_dialog(rows)
        dialog._search_input.setText("camisa balnca")  # typo intencional
        with patch(
            "pos_uniformes.services.meilisearch_service.is_available", return_value=True
        ), patch(
            "pos_uniformes.services.meilisearch_service.search",
            return_value=[{"sku": "SKU-1"}],
        ):
            dialog._run_search()
        # Antes: el filtro local exigía el substring "balnca" → 0 resultados.
        self.assertEqual([r["sku"] for r in dialog._result_rows], ["SKU-1"])

    def test_local_fallback_still_filters_by_all_terms(self) -> None:
        rows = [
            _catalog_row("SKU-1", "Camisa Blanca"),
            _catalog_row("SKU-2", "Camisa Roja", color="Rojo"),
        ]
        dialog = self._make_dialog(rows)
        dialog._search_input.setText("camisa blanca")
        with patch(
            "pos_uniformes.services.meilisearch_service.is_available", return_value=False
        ):
            dialog._run_search()
        self.assertEqual([r["sku"] for r in dialog._result_rows], ["SKU-1"])

    def test_meili_path_still_excludes_inactive_rows(self) -> None:
        inactive = _catalog_row("SKU-3", "Camisa Blanca")
        inactive["variante_activo"] = False
        dialog = self._make_dialog([_catalog_row("SKU-1", "Camisa Blanca"), inactive])
        dialog._search_input.setText("camisa")
        with patch(
            "pos_uniformes.services.meilisearch_service.is_available", return_value=True
        ), patch(
            "pos_uniformes.services.meilisearch_service.search",
            return_value=[{"sku": "SKU-1"}, {"sku": "SKU-3"}],
        ):
            dialog._run_search()
        self.assertEqual([r["sku"] for r in dialog._result_rows], ["SKU-1"])


class SatelliteCatalogSearchTests(unittest.TestCase):
    """El catálogo del satélite no re-aplica el texto cuando Meilisearch ya lo resolvió."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_search_text_not_reapplied_when_meili_used(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        window = QuoteSatelliteWindow(user_id=1)
        window.catalog_snapshot_rows = [{"sku": "SKU-1"}]
        window.catalog_search_input.setText("camisa balnca")
        captured: dict = {}

        def _fake_browser(**kwargs):
            captured.update(kwargs)
            return (), Mock(status_label="")

        with patch(
            "pos_uniformes.services.meilisearch_service.is_available", return_value=True
        ), patch(
            "pos_uniformes.services.meilisearch_service.search",
            return_value=[{"sku": "SKU-1"}],
        ), patch(
            "pos_uniformes.ui.quote_satellite_window.build_quote_catalog_browser",
            side_effect=_fake_browser,
        ):
            window._refresh_catalog_browser()

        self.assertEqual(captured.get("search_text"), "")
        self.assertEqual([r["sku"] for r in captured.get("snapshot_rows", [])], ["SKU-1"])


if __name__ == "__main__":
    unittest.main()
