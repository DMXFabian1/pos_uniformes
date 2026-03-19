from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.catalog_snapshot_service import load_catalog_snapshot_rows


class CatalogSnapshotServiceTests(unittest.TestCase):
    def test_load_catalog_snapshot_rows_builds_snapshot_from_query_rows(self) -> None:
        raw_rows = [
            (
                8,
                2,
                3,
                4,
                None,
                "SKU-008",
                "Uniforme",
                "Marca Norte",
                None,
                "Deportivo",
                None,
                "Pants Deportivo | Morelos | Pants #4",
                "Pants Deportivo",
                "Descripcion",
                "Pants legacy",
                True,
                "16",
                "Azul Marino",
                Decimal("219.00"),
                Decimal("140.00"),
                6,
                2,
                True,
                False,
                True,
            )
        ]
        session = SimpleNamespace()

        with patch(
            "pos_uniformes.services.catalog_snapshot_service._execute_catalog_snapshot_query",
            return_value=raw_rows,
        ):
            snapshot_rows = load_catalog_snapshot_rows(session)

        self.assertEqual(len(snapshot_rows), 1)
        self.assertEqual(snapshot_rows[0]["sku"], "SKU-008")
        self.assertEqual(snapshot_rows[0]["escuela_nombre"], "General")
        self.assertEqual(snapshot_rows[0]["producto_nombre"], "Pants Deportivo | Morelos | Pants")
        self.assertEqual(snapshot_rows[0]["fallback_text"], "fallback")


if __name__ == "__main__":
    unittest.main()
