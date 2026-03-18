from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_users_helper import (
    build_settings_users_error_view,
    build_settings_users_view,
)


class SettingsUsersHelperTests(unittest.TestCase):
    def test_builds_users_view(self) -> None:
        view = build_settings_users_view(
            [
                {
                    "id": 1,
                    "username": "admin",
                    "full_name": "Admin Uno",
                    "role": "ADMIN",
                    "active_label": "ACTIVO",
                    "updated_label": "2026-03-18 10:30",
                },
                {
                    "id": 2,
                    "username": "caja1",
                    "full_name": "Caja Uno",
                    "role": "CAJERO",
                    "active_label": "INACTIVO",
                    "updated_label": "",
                },
            ]
        )

        self.assertEqual(view.status_label, "Usuarios registrados: 2")
        self.assertEqual(len(view.rows), 2)
        self.assertEqual(view.rows[0].user_id, 1)
        self.assertEqual(view.rows[0].values, ("admin", "Admin Uno", "ADMIN", "ACTIVO", "2026-03-18 10:30"))

    def test_builds_error_view(self) -> None:
        view = build_settings_users_error_view("db down")

        self.assertEqual(view.status_label, "No se pudieron cargar usuarios: db down")
        self.assertEqual(view.rows, ())


if __name__ == "__main__":
    unittest.main()
