from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.analytics_snapshot_service import (
    AnalyticsSalesSnapshot,
    build_analytics_sales_snapshot,
    load_confirmed_sales_for_analytics,
)


class AnalyticsSnapshotServiceTests(unittest.TestCase):
    def test_build_analytics_sales_snapshot(self) -> None:
        sales = [
            SimpleNamespace(
                total=Decimal("100.00"),
                cliente_id=1,
                detalles=[SimpleNamespace(cantidad=2), SimpleNamespace(cantidad=1)],
            ),
            SimpleNamespace(
                total=Decimal("50.00"),
                cliente_id=1,
                detalles=[SimpleNamespace(cantidad=1)],
            ),
            SimpleNamespace(
                total=Decimal("75.00"),
                cliente_id=None,
                detalles=[SimpleNamespace(cantidad=3)],
            ),
        ]

        snapshot = build_analytics_sales_snapshot(sales)

        self.assertEqual(
            snapshot,
            AnalyticsSalesSnapshot(
                total_sales=Decimal("225.00"),
                total_tickets=3,
                total_units=7,
                average_ticket=Decimal("75.00"),
                identified_sales_count=2,
                identified_income=Decimal("150.00"),
                repeat_clients=1,
                average_per_client=Decimal("150.00"),
            ),
        )

    def test_load_confirmed_sales_for_analytics_uses_built_statement(self) -> None:
        fake_statement = object()
        session = SimpleNamespace(scalars=lambda statement: [statement, "ok"])

        with patch(
            "pos_uniformes.services.analytics_snapshot_service._build_confirmed_sales_statement",
            return_value=fake_statement,
        ) as statement_mock:
            sales = load_confirmed_sales_for_analytics(
                session,
                period_start=SimpleNamespace(),
                period_end=SimpleNamespace(),
                selected_client_id="12",
            )

        statement_mock.assert_called_once()
        self.assertEqual(sales, [fake_statement, "ok"])


if __name__ == "__main__":
    unittest.main()
