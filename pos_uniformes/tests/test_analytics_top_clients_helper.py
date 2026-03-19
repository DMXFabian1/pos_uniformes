from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.analytics_top_clients_service import AnalyticsTopClientSnapshotRow
from pos_uniformes.ui.helpers.analytics_top_clients_helper import (
    AnalyticsTopClientRowView,
    build_analytics_top_client_row_views,
)


class AnalyticsTopClientsHelperTests(unittest.TestCase):
    def test_build_analytics_top_client_row_views_sets_values_and_tones(self) -> None:
        rows = [
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
        ]

        row_views = build_analytics_top_client_row_views(rows)

        self.assertEqual(
            row_views,
            (
                AnalyticsTopClientRowView(
                    values=("Maria Perez", "C001", 4, Decimal("1200.00")),
                    sales_tone="positive",
                    amount_tone="positive",
                ),
                AnalyticsTopClientRowView(
                    values=("Juan Lopez", "C002", 1, Decimal("280.00")),
                    sales_tone="warning",
                    amount_tone="positive",
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
