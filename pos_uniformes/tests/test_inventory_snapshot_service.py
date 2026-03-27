from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.inventory_snapshot_service import (
    invalidate_inventory_qr_exists_cache,
    load_inventory_snapshot_rows,
)
from pos_uniformes.services.search_filter_service import (
    SEARCH_ALIAS_BLOBS_KEY,
    SEARCH_GENERAL_BLOB_KEY,
)


class InventorySnapshotServiceTests(unittest.TestCase):
    def tearDown(self) -> None:
        invalidate_inventory_qr_exists_cache()

    def test_load_inventory_snapshot_rows_builds_snapshot_from_query_rows(self) -> None:
        raw_rows = [
            (
                8,
                "SKU-008",
                "Uniforme",
                "Marca Norte",
                "Pants Deportivo | Morelos | Pants #4",
                "Pants Deportivo",
                None,
                "Deportivo",
                None,
                "Pants legacy",
                True,
                "16",
                "Azul Marino",
                Decimal("219"),
                Decimal("140"),
                6,
                2,
                False,
                True,
            )
        ]
        session = SimpleNamespace()

        with patch(
            "pos_uniformes.services.inventory_snapshot_service._execute_inventory_snapshot_query",
            return_value=raw_rows,
        ), patch(
            "pos_uniformes.services.inventory_snapshot_service._inventory_qr_exists",
            return_value=True,
        ):
            snapshot_rows = load_inventory_snapshot_rows(session)

        self.assertEqual(len(snapshot_rows), 1)
        row = snapshot_rows[0]
        self.assertEqual(row["sku"], "SKU-008")
        self.assertEqual(row["producto_nombre"], "Pants Deportivo | Morelos | Pants")
        self.assertEqual(row["escuela_nombre"], "General")
        self.assertEqual(row["tipo_pieza_nombre"], "-")
        self.assertEqual(row["precio_venta"], Decimal("219.00"))
        self.assertTrue(row["qr_exists"])
        self.assertEqual(row["fallback_text"], "fallback")
        self.assertIn("pants deportivo", row[SEARCH_GENERAL_BLOB_KEY])
        self.assertIn("pants legacy", row[SEARCH_ALIAS_BLOBS_KEY]["legacy"])

    def test_inventory_qr_exists_is_reused_for_repeated_sku_until_invalidated(self) -> None:
        raw_rows = [
            (
                8,
                "SKU-008",
                "Uniforme",
                "Marca Norte",
                "Pants Deportivo | Morelos | Pants #4",
                "Pants Deportivo",
                None,
                "Deportivo",
                None,
                "Pants legacy",
                True,
                "16",
                "Azul Marino",
                Decimal("219"),
                Decimal("140"),
                6,
                2,
                False,
                True,
            )
        ]
        session = SimpleNamespace()

        with patch(
            "pos_uniformes.services.inventory_snapshot_service._execute_inventory_snapshot_query",
            return_value=raw_rows,
        ), patch(
            "pathlib.Path.exists",
            side_effect=[True, False],
        ) as exists_mock:
            first_rows = load_inventory_snapshot_rows(session)
            second_rows = load_inventory_snapshot_rows(session)
            invalidate_inventory_qr_exists_cache(sku="SKU-008")
            reloaded_rows = load_inventory_snapshot_rows(session)

        self.assertTrue(first_rows[0]["qr_exists"])
        self.assertTrue(second_rows[0]["qr_exists"])
        self.assertFalse(reloaded_rows[0]["qr_exists"])
        self.assertEqual(exists_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
