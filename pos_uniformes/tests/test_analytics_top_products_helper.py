from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.analytics_top_products_service import AnalyticsTopProductSnapshotRow
from pos_uniformes.ui.helpers.analytics_top_products_helper import (
    AnalyticsTopProductRowView,
    build_analytics_top_product_rows,
)


class AnalyticsTopProductsHelperTests(unittest.TestCase):
    def test_build_analytics_top_product_rows_sanitizes_product_name(self) -> None:
        rows = [
            AnalyticsTopProductSnapshotRow(
                sku="SKU-1",
                product_name="Playera Deportiva | Patria | Deportivo | Playera #4",
                units_sold=7,
                revenue=Decimal("840.00"),
            ),
            AnalyticsTopProductSnapshotRow(
                sku="SKU-2",
                product_name="Pantalon de vestir",
                units_sold=3,
                revenue=Decimal("450.00"),
            ),
        ]

        display_rows = build_analytics_top_product_rows(rows)

        self.assertEqual(
            display_rows,
            (
                AnalyticsTopProductRowView(
                    values=("SKU-1", "Playera Deportiva | Patria | Deportivo | Playera", 7, Decimal("840.00")),
                    units_tone="positive",
                    revenue_tone="positive",
                    row_tone="positive",
                ),
                AnalyticsTopProductRowView(
                    values=("SKU-2", "Pantalon de vestir", 3, Decimal("450.00")),
                    units_tone="warning",
                    revenue_tone="warning",
                    row_tone=None,
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
