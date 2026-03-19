from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.analytics_top_clients_service import (
    AnalyticsTopClientSnapshotRow,
    load_analytics_top_client_snapshot_rows,
)


class AnalyticsTopClientsServiceTests(unittest.TestCase):
    def test_load_analytics_top_client_snapshot_rows_maps_raw_rows(self) -> None:
        session = SimpleNamespace()

        with patch(
            "pos_uniformes.services.analytics_top_clients_service._execute_analytics_top_clients_query",
            return_value=[
                ("Maria Perez", "C001", 4, Decimal("1200.00")),
                ("Juan Lopez", "C002", 1, Decimal("280.00")),
            ],
        ) as query_mock:
            rows = load_analytics_top_client_snapshot_rows(
                session,
                period_start=SimpleNamespace(),
                period_end=SimpleNamespace(),
                selected_client_id="7",
            )

        query_mock.assert_called_once()
        self.assertEqual(
            rows,
            (
                AnalyticsTopClientSnapshotRow(
                    client_name="Maria Perez",
                    client_code="C001",
                    sales_count=4,
                    amount=Decimal("1200.00"),
                ),
                AnalyticsTopClientSnapshotRow(
                    client_name="Juan Lopez",
                    client_code="C002",
                    sales_count=1,
                    amount=Decimal("280.00"),
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
