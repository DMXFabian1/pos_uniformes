from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_suppliers_helper import (
    build_settings_suppliers_error_view,
    build_settings_suppliers_view,
)


class SettingsSuppliersHelperTests(unittest.TestCase):
    def test_builds_suppliers_view(self) -> None:
        view = build_settings_suppliers_view(
            [
                {
                    "id": 5,
                    "name": "Proveedor Uno",
                    "phone": "5551234567",
                    "email": "proveedor@example.com",
                    "address": "Calle 1",
                    "active": True,
                    "active_label": "ACTIVO",
                    "updated_label": "2026-03-18 10:30",
                },
                {
                    "id": 6,
                    "name": "Proveedor Dos",
                    "phone": "",
                    "email": "",
                    "address": "",
                    "active": False,
                    "active_label": "INACTIVO",
                    "updated_label": "",
                },
            ]
        )

        self.assertEqual(view.status_label, "Proveedores registrados: 2")
        self.assertEqual(len(view.rows), 2)
        self.assertEqual(view.rows[0].supplier_id, 5)
        self.assertEqual(view.rows[0].status_tone, "positive")
        self.assertEqual(view.rows[1].status_tone, "muted")

    def test_builds_error_view(self) -> None:
        view = build_settings_suppliers_error_view("timeout")

        self.assertEqual(view.status_label, "No se pudieron cargar proveedores: timeout")
        self.assertEqual(view.rows, ())


if __name__ == "__main__":
    unittest.main()
