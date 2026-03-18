from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_clients_helper import (
    build_settings_clients_error_view,
    build_settings_clients_view,
)


class SettingsClientsHelperTests(unittest.TestCase):
    def test_builds_clients_view(self) -> None:
        view = build_settings_clients_view(
            [
                {
                    "id": 7,
                    "code": "CLI-001",
                    "name": "Maria Lopez",
                    "client_type": "PROFESOR",
                    "loyalty_level": "PROFESOR",
                    "discount_label": "15.00%",
                    "has_discount": True,
                    "phone": "5551234567",
                    "notes": "Cliente frecuente",
                    "qr_label": "Listo",
                    "card_label": "Lista",
                    "active": True,
                    "active_label": "ACTIVO",
                    "updated_label": "2026-03-18 10:30",
                },
                {
                    "id": 8,
                    "code": "CLI-002",
                    "name": "Cliente General",
                    "client_type": "GENERAL",
                    "loyalty_level": "BASICO",
                    "discount_label": "0.00%",
                    "has_discount": False,
                    "phone": "",
                    "notes": "",
                    "qr_label": "Pendiente",
                    "card_label": "Pendiente",
                    "active": False,
                    "active_label": "INACTIVO",
                    "updated_label": "",
                },
            ]
        )

        self.assertEqual(view.status_label, "Clientes registrados: 2")
        self.assertEqual(len(view.rows), 2)
        self.assertEqual(view.rows[0].client_id, 7)
        self.assertEqual(view.rows[0].client_code, "CLI-001")
        self.assertEqual(view.rows[0].client_type_tone, "positive")
        self.assertEqual(view.rows[0].loyalty_level_tone, "positive")
        self.assertEqual(view.rows[0].discount_tone, "positive")
        self.assertEqual(view.rows[0].qr_tone, "positive")
        self.assertEqual(view.rows[1].status_tone, "muted")

    def test_builds_error_view(self) -> None:
        view = build_settings_clients_error_view("sqlite busy")

        self.assertEqual(view.status_label, "No se pudieron cargar clientes: sqlite busy")
        self.assertEqual(view.rows, ())


if __name__ == "__main__":
    unittest.main()
