from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.analytics_top_products_service import (
    AnalyticsTopProductSnapshotRow,
    load_analytics_top_product_snapshot_rows,
)


class AnalyticsTopProductsServiceTests(unittest.TestCase):
    def test_load_analytics_top_product_snapshot_rows_maps_raw_rows(self) -> None:
        session = SimpleNamespace()

        with patch(
            "pos_uniformes.services.analytics_top_products_service._execute_analytics_top_products_query",
            return_value=[
                ("SKU-1", "Playera Deportiva | Patria | Deportivo | Playera #4", 7, Decimal("840.00")),
                ("SKU-2", "Pantalon de vestir", 3, Decimal("450.00")),
            ],
        ) as query_mock:
            rows = load_analytics_top_product_snapshot_rows(
                session,
                period_start=SimpleNamespace(),
                period_end=SimpleNamespace(),
                selected_client_id="9",
            )

        query_mock.assert_called_once()
        self.assertEqual(
            rows,
            (
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
            ),
        )


if __name__ == "__main__":
    unittest.main()
