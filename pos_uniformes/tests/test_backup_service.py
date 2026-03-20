from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pos_uniformes.services.backup_service import (
    AutomaticBackupStatus,
    automatic_backup_status_path,
    read_automatic_backup_status,
    run_automatic_backup,
)


class BackupServiceTests(unittest.TestCase):
    def test_run_automatic_backup_updates_status_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            backup_path = output_dir / "pos_uniformes_20260320_020000.dump"
            backup_path.write_text("dump", encoding="utf-8")

            with patch(
                "pos_uniformes.services.backup_service.create_backup",
                return_value=(backup_path, [output_dir / "old.dump"]),
            ):
                _, deleted_files, status = run_automatic_backup(
                    output_dir=output_dir,
                    dump_format="custom",
                    retention_days=14,
                )

            self.assertEqual(deleted_files, [output_dir / "old.dump"])
            self.assertEqual(status.last_backup_path, backup_path)
            self.assertEqual(status.deleted_count, 1)
            saved_status = read_automatic_backup_status(output_dir)
            assert saved_status is not None
            self.assertEqual(saved_status.last_backup_path, backup_path)
            self.assertEqual(saved_status.retention_days, 14)
            self.assertIsNone(saved_status.last_error)

    def test_run_automatic_backup_persists_failure_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            automatic_backup_status_path(output_dir).write_text(
                """{
  "last_run_at": "2026-03-19T02:00:00",
  "last_success_at": "2026-03-19T02:00:00",
  "last_backup_path": "/tmp/prev.dump",
  "dump_format": "custom",
  "retention_days": 14,
  "deleted_count": 0,
  "last_error": null
}""",
                encoding="utf-8",
            )

            with patch(
                "pos_uniformes.services.backup_service.create_backup",
                side_effect=RuntimeError("pg_dump no disponible"),
            ):
                with self.assertRaises(RuntimeError):
                    run_automatic_backup(output_dir=output_dir)

            saved_status = read_automatic_backup_status(output_dir)
            assert saved_status is not None
            self.assertEqual(saved_status.last_backup_path, Path("/tmp/prev.dump"))
            self.assertEqual(saved_status.last_error, "pg_dump no disponible")

    def test_reads_automatic_backup_status_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            automatic_backup_status_path(output_dir).write_text(
                """{
  "last_run_at": "2026-03-20T02:00:00",
  "last_success_at": "2026-03-20T02:00:00",
  "last_backup_path": "/tmp/demo.dump",
  "dump_format": "custom",
  "retention_days": 14,
  "deleted_count": 2,
  "last_error": null
}""",
                encoding="utf-8",
            )

            status = read_automatic_backup_status(output_dir)

            self.assertEqual(
                status,
                AutomaticBackupStatus(
                    last_run_at=datetime(2026, 3, 20, 2, 0),
                    last_success_at=datetime(2026, 3, 20, 2, 0),
                    last_backup_path=Path("/tmp/demo.dump"),
                    dump_format="custom",
                    retention_days=14,
                    deleted_count=2,
                    last_error=None,
                ),
            )


if __name__ == "__main__":
    unittest.main()
