from __future__ import annotations

from datetime import date
from types import SimpleNamespace
import unittest
from unittest.mock import ANY, patch

from pos_uniformes.services.layaway_alerts_service import (
    LayawayAlertsSnapshot,
    load_layaway_alerts_snapshot,
)


class LayawayAlertsServiceTests(unittest.TestCase):
    def test_load_layaway_alerts_snapshot_aggregates_counts(self) -> None:
        with (
            patch(
                "pos_uniformes.services.layaway_alerts_service._count_layaways_overdue",
                return_value=3,
            ) as overdue_mock,
            patch(
                "pos_uniformes.services.layaway_alerts_service._count_layaways_due_today",
                return_value=2,
            ) as today_mock,
            patch(
                "pos_uniformes.services.layaway_alerts_service._count_layaways_due_week",
                return_value=5,
            ) as week_mock,
        ):
            snapshot = load_layaway_alerts_snapshot(SimpleNamespace(), today=date(2026, 3, 19))

        overdue_mock.assert_called_once_with(ANY, today=date(2026, 3, 19))
        today_mock.assert_called_once_with(ANY, today=date(2026, 3, 19))
        week_mock.assert_called_once_with(ANY, today=date(2026, 3, 19), week_limit=date(2026, 3, 26))
        self.assertEqual(snapshot, LayawayAlertsSnapshot(overdue_count=3, due_today_count=2, due_week_count=5))


if __name__ == "__main__":
    unittest.main()
