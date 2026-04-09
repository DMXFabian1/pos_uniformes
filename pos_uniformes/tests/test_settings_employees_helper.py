from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_employees_helper import (
    build_settings_employees_error_view,
    build_settings_employees_view,
)


class SettingsEmployeesHelperTests(unittest.TestCase):
    def test_builds_employees_view(self) -> None:
        view = build_settings_employees_view(
            [
                {
                    "id": 4,
                    "code": "VEND-1",
                    "name": "Guadalupe Gomez Ruiz",
                    "display_name": "Guadalupe Ruiz",
                    "active": True,
                    "active_label": "ACTIVA",
                    "updated_label": "2026-04-09 09:00",
                },
                {
                    "id": 5,
                    "code": "VEND-2",
                    "name": "Andrea Lopez",
                    "display_name": "Andrea Lopez",
                    "active": False,
                    "active_label": "INACTIVA",
                    "updated_label": "",
                },
            ]
        )

        self.assertEqual(view.status_label, "Empleadas registradas: 2")
        self.assertEqual(len(view.rows), 2)
        self.assertEqual(view.rows[0].employee_id, 4)
        self.assertEqual(view.rows[0].status_tone, "positive")
        self.assertEqual(view.rows[1].status_tone, "muted")

    def test_builds_error_view(self) -> None:
        view = build_settings_employees_error_view("db busy")

        self.assertEqual(view.status_label, "No se pudieron cargar empleadas: db busy")
        self.assertEqual(view.rows, ())


if __name__ == "__main__":
    unittest.main()
