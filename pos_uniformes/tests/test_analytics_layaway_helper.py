from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.analytics_layaway_helper import (
    AnalyticsLayawayLabelsView,
    AnalyticsLayawayLabelView,
    build_analytics_layaway_labels_view,
)


class AnalyticsLayawayHelperTests(unittest.TestCase):
    def test_build_analytics_layaway_labels_view_sets_texts_and_tones(self) -> None:
        view = build_analytics_layaway_labels_view(
            active_count=5,
            pending_balance=Decimal("980.50"),
            overdue_count=2,
            delivered_in_period=4,
        )

        self.assertEqual(
            view,
            AnalyticsLayawayLabelsView(
                active=AnalyticsLayawayLabelView("Apartados activos\n5", "positive"),
                balance=AnalyticsLayawayLabelView("Saldo pendiente\n$980.50", "warning"),
                overdue=AnalyticsLayawayLabelView("Vencidos\n2", "danger"),
                delivered=AnalyticsLayawayLabelView("Entregados periodo\n4", "positive"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
