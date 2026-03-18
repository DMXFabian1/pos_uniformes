from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.marketing_history_helper import build_marketing_history_view


class MarketingHistoryHelperTests(unittest.TestCase):
    def test_builds_marketing_history_view(self) -> None:
        view = build_marketing_history_view(
            [
                {
                    "created_at_label": "2026-03-18 12:30",
                    "username": "admin",
                    "role_label": "ADMIN",
                    "section_label": "Lealtad",
                    "field_label": "descuento_leal",
                    "old_value": "10",
                    "new_value": "12",
                }
            ]
        )

        self.assertEqual(view.status_label, "Cambios registrados: 1")
        self.assertEqual(len(view.rows), 1)
        self.assertEqual(
            view.rows[0].values,
            ("2026-03-18 12:30", "admin", "ADMIN", "Lealtad", "descuento_leal", "10", "12"),
        )

    def test_builds_empty_marketing_history_view(self) -> None:
        view = build_marketing_history_view([])

        self.assertEqual(view.status_label, "Aun no hay cambios auditados en Marketing y promociones.")
        self.assertEqual(view.rows, ())


if __name__ == "__main__":
    unittest.main()
