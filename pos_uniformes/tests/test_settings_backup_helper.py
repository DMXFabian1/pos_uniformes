from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_backup_helper import (
    build_settings_backup_error_view,
    build_settings_backup_view,
)


class SettingsBackupHelperTests(unittest.TestCase):
    def test_builds_backup_view_with_rows(self) -> None:
        view = build_settings_backup_view(
            backup_dir="/tmp/backups",
            backups=[
                {
                    "path_value": "/tmp/backups/respaldo_1.dump",
                    "name": "respaldo_1.dump",
                    "format_label": "Dump",
                    "modified_label": "2026-03-18 10:30",
                    "size_label": "5 MB",
                    "restorable_label": "Si",
                },
                {
                    "path_value": "/tmp/backups/respaldo_2.sql",
                    "name": "respaldo_2.sql",
                    "format_label": "SQL",
                    "modified_label": "2026-03-17 09:00",
                    "size_label": "2 MB",
                    "restorable_label": "No",
                },
            ],
        )

        self.assertEqual(view.location_label, "Carpeta de respaldos: /tmp/backups")
        self.assertEqual(view.status_label, "Respaldos disponibles: 2 | Ultimo: respaldo_1.dump")
        self.assertEqual(len(view.rows), 2)
        self.assertEqual(view.rows[0].path_value, "/tmp/backups/respaldo_1.dump")
        self.assertEqual(view.rows[0].values, ("respaldo_1.dump", "Dump", "2026-03-18 10:30", "5 MB", "Si"))

    def test_builds_empty_and_error_states(self) -> None:
        empty_view = build_settings_backup_view(
            backup_dir="/tmp/backups",
            backups=[],
        )
        error_view = build_settings_backup_error_view(
            backup_dir="/tmp/backups",
            error_message="permiso denegado",
        )

        self.assertEqual(empty_view.status_label, "No hay respaldos todavia en la carpeta configurada.")
        self.assertEqual(empty_view.rows, ())
        self.assertEqual(
            error_view.status_label,
            "No se pudo leer la carpeta de respaldos: permiso denegado",
        )
        self.assertEqual(error_view.rows, ())


if __name__ == "__main__":
    unittest.main()
