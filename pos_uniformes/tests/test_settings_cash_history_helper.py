from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_cash_history_helper import build_settings_cash_history_rows


class SettingsCashHistoryHelperTests(unittest.TestCase):
    def test_builds_rows_for_open_and_closed_sessions(self) -> None:
        rows = build_settings_cash_history_rows(
            [
                {
                    "session_id": 12,
                    "is_closed": False,
                    "status_label": "Abierta",
                    "opened_at": "2026-03-18 09:00",
                    "opened_by": "Admin Uno",
                    "opening_amount": "$100.00",
                    "closed_at": "-",
                    "closed_by": "-",
                    "expected_amount": "-",
                    "declared_amount": "-",
                    "difference_amount": "-",
                    "difference": "0.00",
                },
                {
                    "session_id": 13,
                    "is_closed": True,
                    "status_label": "Cerrada",
                    "opened_at": "2026-03-17 09:00",
                    "opened_by": "Admin Uno",
                    "opening_amount": "$100.00",
                    "closed_at": "2026-03-17 19:00",
                    "closed_by": "Admin Dos",
                    "expected_amount": "$500.00",
                    "declared_amount": "$480.00",
                    "difference_amount": "$-20.00",
                    "difference": "-20.00",
                },
            ]
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].session_id, 12)
        self.assertEqual(rows[0].status_tone, "positive")
        self.assertIsNone(rows[0].difference_tone)
        self.assertEqual(rows[1].session_id, 13)
        self.assertEqual(rows[1].status_tone, "muted")
        self.assertEqual(rows[1].difference_tone, "danger")

    def test_marks_positive_and_warning_differences(self) -> None:
        rows = build_settings_cash_history_rows(
            [
                {
                    "session_id": 14,
                    "is_closed": True,
                    "status_label": "Cerrada",
                    "opened_at": "",
                    "opened_by": "",
                    "opening_amount": "$0.00",
                    "closed_at": "",
                    "closed_by": "",
                    "expected_amount": "$0.00",
                    "declared_amount": "$0.00",
                    "difference_amount": "$0.00",
                    "difference": "0.00",
                },
                {
                    "session_id": 15,
                    "is_closed": True,
                    "status_label": "Cerrada",
                    "opened_at": "",
                    "opened_by": "",
                    "opening_amount": "$0.00",
                    "closed_at": "",
                    "closed_by": "",
                    "expected_amount": "$0.00",
                    "declared_amount": "$10.00",
                    "difference_amount": "$10.00",
                    "difference": "10.00",
                },
            ]
        )

        self.assertEqual(rows[0].difference_tone, "positive")
        self.assertEqual(rows[1].difference_tone, "warning")


if __name__ == "__main__":
    unittest.main()
