from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pos_uniformes.utils.config import (
    Settings,
    load_runtime_env_overrides,
    server_db_host,
    server_db_port,
)


class ConfigTests(unittest.TestCase):
    def test_load_runtime_env_overrides_reads_pos_uniformes_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / "pos_uniformes.env"
            env_path.write_text(
                "\n".join(
                    [
                        "# Comentario",
                        "POS_UNIFORMES_DB_HOST=servidor-local",
                        "POS_UNIFORMES_DB_PORT=5544",
                        "POS_UNIFORMES_DB_NAME=uniformes_demo",
                    ]
                ),
                encoding="utf-8",
            )

            overrides = load_runtime_env_overrides(Path(temp_dir))

        self.assertEqual(
            overrides,
            {
                "POS_UNIFORMES_DB_HOST": "servidor-local",
                "POS_UNIFORMES_DB_PORT": "5544",
                "POS_UNIFORMES_DB_NAME": "uniformes_demo",
            },
        )

    def test_settings_from_env_uses_runtime_env_file_as_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / "pos_uniformes.env"
            env_path.write_text(
                "\n".join(
                    [
                        "POS_UNIFORMES_DB_HOST=servidor-local",
                        "POS_UNIFORMES_DB_PORT=5544",
                        "POS_UNIFORMES_DB_NAME=uniformes_demo",
                        "POS_UNIFORMES_DB_USER=operador",
                        "POS_UNIFORMES_DB_PASSWORD=secreto",
                        "POS_UNIFORMES_DB_ECHO=1",
                        "POS_UNIFORMES_AUTO_CREATE_SCHEMA=true",
                        "POS_UNIFORMES_BACKUP_EXTERNAL_DIR=/tmp/respaldos-externos",
                    ]
                ),
                encoding="utf-8",
            )

            with patch(
                "pos_uniformes.utils.config.load_runtime_env_overrides",
                return_value=load_runtime_env_overrides(Path(temp_dir)),
            ), patch.dict("os.environ", {}, clear=True):
                settings = Settings.from_env()

        self.assertEqual(settings.db_host, "servidor-local")
        self.assertEqual(settings.db_port, 5544)
        self.assertEqual(settings.db_name, "uniformes_demo")
        self.assertEqual(settings.db_user, "operador")
        self.assertEqual(settings.db_password, "secreto")
        self.assertTrue(settings.db_echo)
        self.assertTrue(settings.auto_create_schema)
        self.assertEqual(settings.backup_external_dir, "/tmp/respaldos-externos")

    def test_settings_from_env_prefers_real_environment_over_file(self) -> None:
        with patch(
            "pos_uniformes.utils.config.load_runtime_env_overrides",
            return_value={"POS_UNIFORMES_DB_HOST": "archivo"},
        ), patch.dict("os.environ", {"POS_UNIFORMES_DB_HOST": "entorno"}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.db_host, "entorno")
        self.assertIsNone(settings.backup_external_dir)


class ServerHostTests(unittest.TestCase):
    """La IP del servidor vive solo en el .env — nunca codificada en el codigo."""

    def test_prefers_server_host_over_db_host(self) -> None:
        with patch(
            "pos_uniformes.utils.config.load_runtime_env_overrides",
            return_value={
                "POS_UNIFORMES_SERVER_HOST": "192.168.0.10",
                "POS_UNIFORMES_DB_HOST": "localhost",
            },
        ), patch.dict("os.environ", {}, clear=True):
            self.assertEqual(server_db_host(), "192.168.0.10")

    def test_falls_back_to_db_host(self) -> None:
        with patch(
            "pos_uniformes.utils.config.load_runtime_env_overrides",
            return_value={"POS_UNIFORMES_DB_HOST": "192.168.0.10"},
        ), patch.dict("os.environ", {}, clear=True):
            self.assertEqual(server_db_host(), "192.168.0.10")

    def test_real_environment_wins_over_file(self) -> None:
        with patch(
            "pos_uniformes.utils.config.load_runtime_env_overrides",
            return_value={"POS_UNIFORMES_SERVER_HOST": "archivo"},
        ), patch.dict("os.environ", {"POS_UNIFORMES_SERVER_HOST": "entorno"}, clear=True):
            self.assertEqual(server_db_host(), "entorno")

    def test_returns_none_when_nothing_configured(self) -> None:
        with patch(
            "pos_uniformes.utils.config.load_runtime_env_overrides",
            return_value={},
        ), patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(server_db_host())

    def test_ignores_blank_value(self) -> None:
        with patch(
            "pos_uniformes.utils.config.load_runtime_env_overrides",
            return_value={"POS_UNIFORMES_SERVER_HOST": "   ", "POS_UNIFORMES_DB_HOST": "192.168.0.10"},
        ), patch.dict("os.environ", {}, clear=True):
            self.assertEqual(server_db_host(), "192.168.0.10")

    def test_port_read_from_file_and_defaults_when_invalid(self) -> None:
        with patch(
            "pos_uniformes.utils.config.load_runtime_env_overrides",
            return_value={"POS_UNIFORMES_DB_PORT": "5544"},
        ), patch.dict("os.environ", {}, clear=True):
            self.assertEqual(server_db_port(), 5544)

        with patch(
            "pos_uniformes.utils.config.load_runtime_env_overrides",
            return_value={"POS_UNIFORMES_DB_PORT": "no-es-numero"},
        ), patch.dict("os.environ", {}, clear=True):
            self.assertEqual(server_db_port(), 5432)


if __name__ == "__main__":
    unittest.main()
