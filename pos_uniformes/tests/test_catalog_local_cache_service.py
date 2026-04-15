"""Tests para catalog_local_cache_service."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import json
import unittest
from unittest.mock import patch


class SaveLoadRoundTripTests(unittest.TestCase):

    def _make_tmp_path(self, tmp_dir: Path) -> Path:
        return tmp_dir / "data" / "catalog_cache.json"

    def test_save_then_load_returns_same_rows(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch("pos_uniformes.services.catalog_local_cache_service.satellite_data_dir", return_value=tmp_path):
                from pos_uniformes.services.catalog_local_cache_service import save_catalog_cache, load_catalog_cache
                rows = [{"sku": "ABC-001", "precio_venta": "150.00", "producto_activo": True}]
                save_catalog_cache(rows)
                result = load_catalog_cache()
        self.assertEqual(result, rows)

    def test_decimal_serialized_as_string(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch("pos_uniformes.services.catalog_local_cache_service.satellite_data_dir", return_value=tmp_path):
                from pos_uniformes.services.catalog_local_cache_service import save_catalog_cache, load_catalog_cache
                rows = [{"precio_venta": Decimal("99.99")}]
                save_catalog_cache(rows)
                result = load_catalog_cache()
        self.assertEqual(result[0]["precio_venta"], "99.99")

    def test_load_returns_none_when_no_cache(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch("pos_uniformes.services.catalog_local_cache_service.satellite_data_dir", return_value=tmp_path):
                from pos_uniformes.services.catalog_local_cache_service import load_catalog_cache
                result = load_catalog_cache()
        self.assertIsNone(result)

    def test_load_returns_none_on_corrupt_file(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_file = tmp_path / "data" / "catalog_cache.json"
            cache_file.parent.mkdir(parents=True)
            cache_file.write_text("esto no es json valido", encoding="utf-8")
            with patch("pos_uniformes.services.catalog_local_cache_service.satellite_data_dir", return_value=tmp_path):
                from pos_uniformes.services.catalog_local_cache_service import load_catalog_cache
                result = load_catalog_cache()
        self.assertIsNone(result)

    def test_load_returns_none_when_rows_missing(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_file = tmp_path / "data" / "catalog_cache.json"
            cache_file.parent.mkdir(parents=True)
            cache_file.write_text(json.dumps({"saved_at": "2026-04-14T00:00:00+00:00"}), encoding="utf-8")
            with patch("pos_uniformes.services.catalog_local_cache_service.satellite_data_dir", return_value=tmp_path):
                from pos_uniformes.services.catalog_local_cache_service import load_catalog_cache
                result = load_catalog_cache()
        self.assertIsNone(result)

    def test_saved_at_is_recorded(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch("pos_uniformes.services.catalog_local_cache_service.satellite_data_dir", return_value=tmp_path):
                from pos_uniformes.services.catalog_local_cache_service import save_catalog_cache, catalog_cache_saved_at
                save_catalog_cache([{"sku": "X"}])
                saved = catalog_cache_saved_at()
        self.assertIsNotNone(saved)
        self.assertIn("T", saved)  # formato ISO

    def test_catalog_cache_saved_at_none_when_no_file(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch("pos_uniformes.services.catalog_local_cache_service.satellite_data_dir", return_value=tmp_path):
                from pos_uniformes.services.catalog_local_cache_service import catalog_cache_saved_at
                result = catalog_cache_saved_at()
        self.assertIsNone(result)

    def test_save_creates_parent_dirs(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch("pos_uniformes.services.catalog_local_cache_service.satellite_data_dir", return_value=tmp_path):
                from pos_uniformes.services.catalog_local_cache_service import save_catalog_cache
                save_catalog_cache([])
            self.assertTrue((tmp_path / "data" / "catalog_cache.json").exists())


class FormatCacheAgeLabelTests(unittest.TestCase):

    def test_valid_iso_formats_correctly(self) -> None:
        from pos_uniformes.services.catalog_local_cache_service import format_cache_age_label
        label = format_cache_age_label("2026-04-14T15:30:00+00:00")
        self.assertIn("14/04/2026", label)
        self.assertIn("guardado el", label)

    def test_invalid_iso_returns_fallback(self) -> None:
        from pos_uniformes.services.catalog_local_cache_service import format_cache_age_label
        label = format_cache_age_label("esto-no-es-fecha")
        self.assertEqual(label, "guardado anteriormente")


if __name__ == "__main__":
    unittest.main()
