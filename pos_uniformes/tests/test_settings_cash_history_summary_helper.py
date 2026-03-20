from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_cash_history_summary_helper import (
    build_settings_cash_history_status_label,
)


class SettingsCashHistorySummaryHelperTests(unittest.TestCase):
    def test_builds_status_label(self) -> None:
        label = build_settings_cash_history_status_label(
            total_sessions=12,
            open_sessions=1,
            closed_sessions=11,
            date_from_iso="2026-02-17",
            date_to_iso="2026-03-18",
        )

        self.assertEqual(
            label,
            "Cortes registrados: 12 | Abiertas: 1 | Cerradas: 11 | Rango: 17/02/2026 a 18/03/2026",
        )


if __name__ == "__main__":
    unittest.main()
