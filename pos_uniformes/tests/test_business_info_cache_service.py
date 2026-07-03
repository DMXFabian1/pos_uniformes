"""Tests del cache local de info del negocio (tickets offline)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services.business_info_cache_service import (
    load_business_info,
    save_business_info,
)

_MOD = "pos_uniformes.services.business_info_cache_service.satellite_data_dir"


class BusinessInfoCacheTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_MOD, return_value=Path(d)):
                save_business_info("MAXIMODA", "555-1234", "Centro 10")
                self.assertEqual(
                    load_business_info(), ("MAXIMODA", "555-1234", "Centro 10")
                )

    def test_load_missing_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_MOD, return_value=Path(d)):
                self.assertIsNone(load_business_info())

    def test_load_corrupt_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_MOD, return_value=Path(d)):
                cache = Path(d) / "data" / "business_info.json"
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text("{ not json", encoding="utf-8")
                self.assertIsNone(load_business_info())


if __name__ == "__main__":
    unittest.main()
