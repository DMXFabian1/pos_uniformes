from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.layaway_alerts_helper import build_layaway_alerts_view


class LayawayAlertsHelperTests(unittest.TestCase):
    def test_builds_rich_alerts_and_quick_summary(self) -> None:
        view = build_layaway_alerts_view(
            overdue_count=2,
            due_today_count=1,
            due_week_count=4,
        )

        self.assertIn("Vencidos: 2", view.alerts_rich_text)
        self.assertIn("Hoy: 1", view.alerts_rich_text)
        self.assertIn("7 dias: 4", view.alerts_rich_text)
        self.assertEqual(
            view.quick_alerts_text,
            "Apartados vencidos: 2 | Vencen hoy: 1 | Proximos 7 dias: 4",
        )

    def test_uses_neutral_badges_when_counts_are_zero(self) -> None:
        view = build_layaway_alerts_view(
            overdue_count=0,
            due_today_count=0,
            due_week_count=0,
        )

        self.assertIn("Vencidos: 0", view.alerts_rich_text)
        self.assertIn("#ecd5c5", view.alerts_rich_text)
        self.assertEqual(
            view.quick_alerts_text,
            "Apartados vencidos: 0 | Vencen hoy: 0 | Proximos 7 dias: 0",
        )


if __name__ == "__main__":
    unittest.main()
