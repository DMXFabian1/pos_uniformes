from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.analytics_stock_service import (
    AnalyticsStockSnapshotRow,
    load_analytics_stock_snapshot_rows,
)


class AnalyticsStockServiceTests(unittest.TestCase):
    def test_load_analytics_stock_snapshot_rows_maps_raw_rows(self) -> None:
        session = SimpleNamespace()

        with patch(
            "pos_uniformes.services.analytics_stock_service._execute_analytics_stock_query",
            return_value=[
                ("SKU-1", "Playera Deportiva | Patria | Deportivo | Playera #4", 0, 2, False),
                ("SKU-2", "Pantalon de vestir", 3, 0, True),
            ],
        ) as query_mock:
            rows = load_analytics_stock_snapshot_rows(session, limit=10)

        query_mock.assert_called_once_with(session, limit=10)
        self.assertEqual(
            rows,
            (
                AnalyticsStockSnapshotRow("SKU-1", "Playera Deportiva | Patria | Deportivo | Playera #4", 0, 2, False),
                AnalyticsStockSnapshotRow("SKU-2", "Pantalon de vestir", 3, 0, True),
            ),
        )


if __name__ == "__main__":
    unittest.main()
