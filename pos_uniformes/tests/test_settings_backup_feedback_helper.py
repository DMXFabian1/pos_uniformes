from __future__ import annotations

from pathlib import Path
import unittest

from pos_uniformes.ui.helpers.settings_backup_feedback_helper import (
    SettingsBackupFeedbackView,
    build_settings_backup_guard_feedback,
    build_settings_backup_restore_confirmation,
    build_settings_backup_result_feedback,
)


class SettingsBackupFeedbackHelperTests(unittest.TestCase):
    def test_build_settings_backup_guard_feedback(self) -> None:
        self.assertEqual(
            build_settings_backup_guard_feedback("create_backup", is_admin=False),
            SettingsBackupFeedbackView(
                title="Sin permisos",
                message="Solo ADMIN puede crear respaldos manuales.",
            ),
        )
        self.assertEqual(
            build_settings_backup_guard_feedback("restore_backup", is_admin=True, backup_path=None),
            SettingsBackupFeedbackView(
                title="Sin seleccion",
                message="Selecciona un respaldo en la tabla.",
            ),
        )
        self.assertEqual(
            build_settings_backup_guard_feedback(
                "restore_backup",
                is_admin=True,
                backup_path=Path("/tmp/demo.sql"),
            ),
            SettingsBackupFeedbackView(
                title="Formato no soportado",
                message="La restauracion desde la app solo soporta respaldos .dump. Crea uno en formato restaurable.",
            ),
        )
        self.assertIsNone(
            build_settings_backup_guard_feedback(
                "restore_backup",
                is_admin=True,
                backup_path=Path("/tmp/demo.dump"),
            )
        )

    def test_build_settings_backup_restore_confirmation(self) -> None:
        view = build_settings_backup_restore_confirmation("demo.dump")
        self.assertEqual(view.title, "Restaurar respaldo")
        self.assertIn("demo.dump", view.message)
        self.assertIn("Deseas continuar?", view.message)

    def test_build_settings_backup_result_feedback(self) -> None:
        self.assertEqual(
            build_settings_backup_result_feedback("create_backup", backup_name="demo.dump", deleted_count=2),
            SettingsBackupFeedbackView(
                title="Respaldo creado",
                message="Se genero demo.dump | Rotacion elimino 2 respaldo(s).",
            ),
        )
        self.assertEqual(
            build_settings_backup_result_feedback("restore_backup", backup_name="demo.dump"),
            SettingsBackupFeedbackView(
                title="Restauracion completada",
                message="Se restauro demo.dump correctamente.",
            ),
        )


if __name__ == "__main__":
    unittest.main()
