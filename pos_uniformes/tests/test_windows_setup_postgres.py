from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pos_uniformes.scripts import windows_setup_postgres


class WindowsSetupPostgresTests(unittest.TestCase):
    def test_parse_args_defaults(self) -> None:
        args = windows_setup_postgres.parse_args([])

        self.assertFalse(args.install_postgres)
        self.assertEqual(args.db_host, "localhost")
        self.assertEqual(args.db_port, "5432")
        self.assertEqual(args.db_name, "pos_uniformes")
        self.assertEqual(args.db_user, "postgres")
        self.assertFalse(args.skip_migrations)
        self.assertFalse(args.skip_precheck)
        self.assertFalse(args.dry_run)

    def test_replace_env_value_updates_existing_key(self) -> None:
        content = "POS_UNIFORMES_DB_HOST=localhost\nPOS_UNIFORMES_DB_PORT=5432\n"

        updated = windows_setup_postgres.replace_env_value(content, "POS_UNIFORMES_DB_PORT", "5433")

        self.assertIn("POS_UNIFORMES_DB_PORT=5433", updated)
        self.assertNotIn("POS_UNIFORMES_DB_PORT=5432", updated)

    def test_replace_env_value_appends_missing_key(self) -> None:
        content = "POS_UNIFORMES_DB_HOST=localhost\n"

        updated = windows_setup_postgres.replace_env_value(content, "POS_UNIFORMES_DB_NAME", "pos_uniformes")

        self.assertTrue(updated.endswith("POS_UNIFORMES_DB_NAME=pos_uniformes\n"))

    def test_write_env_file_updates_project_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            example = root / "pos_uniformes.env.example"
            example.write_text(
                "POS_UNIFORMES_DB_HOST=localhost\n"
                "POS_UNIFORMES_DB_PORT=5432\n"
                "POS_UNIFORMES_DB_NAME=demo\n"
                "POS_UNIFORMES_DB_USER=postgres\n"
                "POS_UNIFORMES_DB_PASSWORD=postgres\n"
                "POS_UNIFORMES_AUTO_CREATE_SCHEMA=0\n",
                encoding="utf-8",
            )
            env_file = root / "pos_uniformes.env"
            env_file.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

            args = windows_setup_postgres.parse_args(
                [
                    "--db-host",
                    "127.0.0.1",
                    "--db-port",
                    "5433",
                    "--db-name",
                    "pos_uniformes",
                    "--db-user",
                    "app",
                    "--db-password",
                    "secret",
                ]
            )

            target = windows_setup_postgres.write_env_file(root, args, dry_run=False)

            content = target.read_text(encoding="utf-8")
            self.assertIn("POS_UNIFORMES_DB_HOST=127.0.0.1", content)
            self.assertIn("POS_UNIFORMES_DB_PORT=5433", content)
            self.assertIn("POS_UNIFORMES_DB_NAME=pos_uniformes", content)
            self.assertIn("POS_UNIFORMES_DB_USER=app", content)
            self.assertIn("POS_UNIFORMES_DB_PASSWORD=secret", content)


if __name__ == "__main__":
    unittest.main()
