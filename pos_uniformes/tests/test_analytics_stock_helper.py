from __future__ import annotations

import unittest

from pos_uniformes.services.analytics_stock_service import AnalyticsStockSnapshotRow
from pos_uniformes.ui.helpers.analytics_stock_helper import (
    AnalyticsStockRowView,
    build_analytics_stock_row_views,
)


class AnalyticsStockHelperTests(unittest.TestCase):
    def test_build_analytics_stock_row_views_sets_values_and_tones(self) -> None:
        rows = [
            AnalyticsStockSnapshotRow(
                sku="SKU-1",
                product_name="Playera Deportiva | Patria | Deportivo | Playera #4",
                stock_actual=0,
                reserved_quantity=2,
                is_active=False,
            ),
            AnalyticsStockSnapshotRow(
                sku="SKU-2",
                product_name="Pantalon de vestir",
                stock_actual=3,
                reserved_quantity=0,
                is_active=True,
            ),
        ]

        row_views = build_analytics_stock_row_views(rows)

        self.assertEqual(
            row_views,
            (
                AnalyticsStockRowView(
                    values=("SKU-1", "Playera Deportiva | Patria | Deportivo | Playera", 0, 2, "INACTIVA"),
                    stock_tone="danger",
                    reserved_tone="warning",
                    state_tone="muted",
                    row_tone="danger",
                ),
                AnalyticsStockRowView(
                    values=("SKU-2", "Pantalon de vestir", 3, 0, "ACTIVA"),
                    stock_tone="warning",
                    reserved_tone="muted",
                    state_tone="positive",
                    row_tone="warning",
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
