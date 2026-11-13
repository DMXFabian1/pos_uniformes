from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_clients_helper import (
    build_settings_clients_error_view,
)


class SettingsClientsHelperTests(unittest.TestCase):
    def test_builds_error_view(self) -> None:
        view = build_settings_clients_error_view("sqlite busy")

        self.assertEqual(view.status_label, "No se pudieron cargar clientes: sqlite busy")
        self.assertEqual(view.rows, ())


if __name__ == "__main__":
    unittest.main()
