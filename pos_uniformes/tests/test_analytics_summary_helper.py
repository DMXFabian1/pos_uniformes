from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import unittest

from pos_uniformes.services.analytics_snapshot_service import AnalyticsSalesSnapshot
from pos_uniformes.services.backup_service import AutomaticBackupStatus
from pos_uniformes.ui.helpers.analytics_summary_helper import (
    build_analytics_alerts_text,
    build_analytics_operational_alerts,
    build_analytics_summary_trend_view,
)


class AnalyticsSummaryHelperTests(unittest.TestCase):
    def test_build_analytics_summary_trend_view(self) -> None:
        current = AnalyticsSalesSnapshot(
            total_sales=Decimal("1000.00"),
            total_tickets=5,
            total_units=9,
            average_ticket=Decimal("200.00"),
            identified_sales_count=3,
            identified_income=Decimal("700.00"),
            repeat_clients=1,
            average_per_client=Decimal("350.00"),
        )
        previous = AnalyticsSalesSnapshot(
            total_sales=Decimal("800.00"),
            total_tickets=4,
            total_units=8,
            average_ticket=Decimal("200.00"),
            identified_sales_count=2,
            identified_income=Decimal("500.00"),
            repeat_clients=1,
            average_per_client=Decimal("250.00"),
        )

        trend = build_analytics_summary_trend_view(current, previous)

        self.assertIn("Subio", trend.sales.text)
        self.assertEqual(trend.sales.tone, "positive")
        self.assertEqual(trend.average.text, "Sin cambio vs periodo anterior")

    def test_build_analytics_operational_alerts(self) -> None:
        alerts = build_analytics_operational_alerts(
            stock_critical_count=12,
            overdue_layaways=2,
            automatic_backup_status=AutomaticBackupStatus(
                last_run_at=datetime(2026, 3, 18, 2, 0),
                last_success_at=datetime(2026, 3, 18, 2, 0),
                last_backup_path=None,
                dump_format="custom",
                retention_days=14,
                deleted_count=0,
                last_error=None,
            ),
            now=datetime(2026, 3, 20, 20, 0),
        )

        self.assertEqual(
            alerts,
            (
                "Stock critico alto: 12 presentaciones.",
                "Apartados vencidos: 2.",
                "Ultimo respaldo automatico ya esta viejo.",
            ),
        )
        self.assertIn("Stock critico alto", build_analytics_alerts_text(alerts))


if __name__ == "__main__":
    unittest.main()
