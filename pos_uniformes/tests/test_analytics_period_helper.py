from __future__ import annotations

from datetime import date, datetime
import unittest

from pos_uniformes.ui.helpers.analytics_period_helper import (
    ANALYTICS_QUICK_PERIODS,
    build_analytics_export_status_text,
    is_manual_analytics_period,
    resolve_previous_analytics_period_bounds,
    resolve_analytics_period_bounds,
)


class AnalyticsPeriodHelperTests(unittest.TestCase):
    def test_is_manual_analytics_period(self) -> None:
        self.assertTrue(is_manual_analytics_period("manual"))
        self.assertFalse(is_manual_analytics_period("7d"))

    def test_resolve_analytics_period_bounds_swaps_manual_dates_when_needed(self) -> None:
        start, end = resolve_analytics_period_bounds(
            "manual",
            today=date(2026, 3, 19),
            manual_from=date(2026, 3, 20),
            manual_to=date(2026, 3, 10),
        )

        self.assertEqual(start, datetime(2026, 3, 10, 0, 0, 0))
        self.assertEqual(end, datetime(2026, 3, 21, 0, 0, 0))

    def test_resolve_analytics_period_bounds_for_7d(self) -> None:
        start, end = resolve_analytics_period_bounds("7d", today=date(2026, 3, 19))

        self.assertEqual(start, datetime(2026, 3, 13, 0, 0, 0))
        self.assertEqual(end, datetime(2026, 3, 20, 0, 0, 0))

    def test_resolve_analytics_period_bounds_for_month(self) -> None:
        start, end = resolve_analytics_period_bounds("month", today=date(2026, 3, 19))

        self.assertEqual(start, datetime(2026, 3, 1, 0, 0, 0))
        self.assertEqual(end, datetime(2026, 3, 20, 0, 0, 0))

    def test_build_analytics_export_status_text(self) -> None:
        self.assertEqual(
            build_analytics_export_status_text(selected_client_id=None, selected_client_label="Cliente X"),
            "Periodo listo para analisis. Cliente: todos.",
        )
        self.assertEqual(
            build_analytics_export_status_text(selected_client_id=7, selected_client_label="Cliente X"),
            "Periodo listo para analisis. Cliente: Cliente X.",
        )

    def test_quick_periods_and_previous_bounds(self) -> None:
        self.assertEqual(
            ANALYTICS_QUICK_PERIODS,
            (("Hoy", "today"), ("7 dias", "7d"), ("30 dias", "30d"), ("Mes actual", "month")),
        )
        start, end = resolve_previous_analytics_period_bounds(
            period_start=datetime(2026, 3, 13, 0, 0, 0),
            period_end=datetime(2026, 3, 20, 0, 0, 0),
        )
        self.assertEqual(start, datetime(2026, 3, 6, 0, 0, 0))
        self.assertEqual(end, datetime(2026, 3, 13, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
