from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import unittest

from pos_uniformes.services.history_snapshot_service import (
    HistorySnapshotFilters,
    load_history_snapshot_rows,
)


class HistorySnapshotServiceTests(unittest.TestCase):
    def test_load_history_snapshot_rows_combines_inventory_and_catalog(self) -> None:
        filters = HistorySnapshotFilters(
            source_filter="",
            entity_filter="",
            sku_filter="sku",
            type_filter="",
            start_datetime=None,
            end_datetime=None,
        )
        rows = load_history_snapshot_rows(
            object(),
            filters=filters,
            inventory_loader=lambda session, current_filters: [
                {"fecha": datetime(2026, 3, 18), "origen": "Inventario"}
            ],
            catalog_loader=lambda session, current_filters: [
                {"fecha": datetime(2026, 3, 17), "origen": "Catalogo"}
            ],
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["origen"], "Inventario")
        self.assertEqual(rows[1]["origen"], "Catalogo")

    def test_load_history_snapshot_rows_respects_source_filter(self) -> None:
        filters = HistorySnapshotFilters(
            source_filter="catalog",
            entity_filter="",
            sku_filter="",
            type_filter="",
            start_datetime=None,
            end_datetime=None,
        )
        rows = load_history_snapshot_rows(
            object(),
            filters=filters,
            inventory_loader=lambda session, current_filters: [{"origen": "Inventario"}],
            catalog_loader=lambda session, current_filters: [{"origen": "Catalogo"}],
        )

        self.assertEqual(rows, [{"origen": "Catalogo"}])


if __name__ == "__main__":
    unittest.main()
