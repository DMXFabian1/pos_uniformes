from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pos_uniformes.services.settings_backup_action_service import (
    SettingsBackupCreateResult,
    create_settings_backup,
    open_settings_backup_folder,
    restore_settings_backup,
)


class SettingsBackupActionServiceTests(unittest.TestCase):
    def test_create_settings_backup_uses_default_output_dir(self) -> None:
        backup_file = Path("/tmp/demo.dump")
        deleted = [Path("/tmp/old.dump")]
        with patch(
            "pos_uniformes.services.settings_backup_action_service.create_backup",
            return_value=(backup_file, deleted),
        ) as create_backup_mock:
            result = create_settings_backup(dump_format="custom", retention_days=3)

        self.assertEqual(
            result,
            SettingsBackupCreateResult(
                backup_file=backup_file,
                deleted_files=(Path("/tmp/old.dump"),),
            ),
        )
        create_backup_mock.assert_called_once()
        self.assertEqual(create_backup_mock.call_args.kwargs["dump_format"], "custom")
        self.assertEqual(create_backup_mock.call_args.kwargs["retention_days"], 3)

    def test_open_settings_backup_folder_creates_dir_and_calls_injected_opener(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "backups"
            opened: list[Path] = []
            with patch(
                "pos_uniformes.services.settings_backup_action_service.backup_output_dir",
                return_value=target_dir,
            ):
                result = open_settings_backup_folder(open_path=opened.append)

            self.assertTrue(target_dir.exists())

        self.assertEqual(result, target_dir)
        self.assertEqual(opened, [target_dir])

    def test_restore_settings_backup_disposes_before_restore(self) -> None:
        events: list[str] = []
        with patch("pos_uniformes.services.settings_backup_action_service.restore_backup") as restore_backup_mock:
            result = restore_settings_backup(
                Path("/tmp/demo.dump"),
                dispose_database=lambda: events.append("disposed"),
            )

        self.assertEqual(result, Path("/tmp/demo.dump"))
        self.assertEqual(events, ["disposed"])
        restore_backup_mock.assert_called_once_with(Path("/tmp/demo.dump"))


if __name__ == "__main__":
    unittest.main()
