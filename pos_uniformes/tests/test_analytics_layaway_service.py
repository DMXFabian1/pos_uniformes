from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import ANY, patch

from pos_uniformes.services.analytics_layaway_service import (
    AnalyticsLayawaySnapshot,
    load_analytics_layaway_snapshot,
)


class AnalyticsLayawayServiceTests(unittest.TestCase):
    def test_load_analytics_layaway_snapshot_aggregates_counts(self) -> None:
        session = SimpleNamespace()

        with (
            patch(
                "pos_uniformes.services.analytics_layaway_service._count_active_layaways",
                return_value=5,
            ) as active_mock,
            patch(
                "pos_uniformes.services.analytics_layaway_service._sum_pending_balance",
                return_value=Decimal("980.50"),
            ) as balance_mock,
            patch(
                "pos_uniformes.services.analytics_layaway_service._count_overdue_layaways",
                return_value=2,
            ) as overdue_mock,
            patch(
                "pos_uniformes.services.analytics_layaway_service._count_delivered_layaways",
                return_value=4,
            ) as delivered_mock,
        ):
            snapshot = load_analytics_layaway_snapshot(
                session,
                period_start=SimpleNamespace(),
                period_end=SimpleNamespace(),
                today=date(2026, 3, 19),
            )

        active_mock.assert_called_once_with(session)
        balance_mock.assert_called_once_with(session)
        overdue_mock.assert_called_once_with(session, today=date(2026, 3, 19))
        delivered_mock.assert_called_once_with(session, period_start=ANY, period_end=ANY)
        self.assertEqual(
            snapshot,
            AnalyticsLayawaySnapshot(
                active_count=5,
                pending_balance=Decimal("980.50"),
                overdue_count=2,
                delivered_in_period=4,
            ),
        )


if __name__ == "__main__":
    unittest.main()
