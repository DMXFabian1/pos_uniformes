from __future__ import annotations

from datetime import datetime
import unittest

from pos_uniformes.ui.helpers.settings_backup_helper import (
    build_settings_backup_automatic_status_view,
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
        self.assertEqual(view.automatic_status_label, "Automatico: sin informacion todavia.")
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
        self.assertEqual(empty_view.automatic_status_label, "Automatico: sin informacion todavia.")
        self.assertEqual(
            error_view.status_label,
            "No se pudo leer la carpeta de respaldos: permiso denegado",
        )
        self.assertEqual(error_view.rows, ())

    def test_formats_automatic_status_as_ok_or_revisar(self) -> None:
        ok_summary, ok_detail = build_settings_backup_automatic_status_view(
            automatic_status={
                "last_run_at": datetime(2026, 3, 20, 2, 0),
                "last_success_at": datetime(2026, 3, 20, 2, 0),
                "backup_name": "pos_uniformes_20260320_020000.dump",
                "retention_days": 14,
                "last_error": None,
            },
            now=datetime(2026, 3, 20, 10, 0),
        )
        stale_summary, stale_detail = build_settings_backup_automatic_status_view(
            automatic_status={
                "last_run_at": datetime(2026, 3, 18, 2, 0),
                "last_success_at": datetime(2026, 3, 18, 2, 0),
                "backup_name": "pos_uniformes_20260318_020000.dump",
                "retention_days": 14,
                "last_error": None,
            },
            now=datetime(2026, 3, 20, 20, 0),
        )

        self.assertIn("Automatico: OK", ok_summary)
        self.assertIn("pos_uniformes_20260320_020000.dump", ok_detail)
        self.assertIn("Automatico: revisar", stale_summary)
        self.assertIn("18/03/2026 02:00", stale_detail)

    def test_formats_automatic_status_error(self) -> None:
        summary, detail = build_settings_backup_automatic_status_view(
            automatic_status={
                "last_run_at": datetime(2026, 3, 20, 2, 0),
                "last_success_at": datetime(2026, 3, 19, 2, 0),
                "backup_name": "pos_uniformes_20260319_020000.dump",
                "retention_days": 14,
                "last_error": "pg_dump fallo",
            },
            now=datetime(2026, 3, 20, 10, 0),
        )

        self.assertIn("fallo en la ultima ejecucion", summary)
        self.assertIn("pg_dump fallo", detail)


if __name__ == "__main__":
    unittest.main()
