from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pos_uniformes.utils.config import Settings, load_runtime_env_overrides


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

    def test_settings_from_env_prefers_real_environment_over_file(self) -> None:
        with patch(
            "pos_uniformes.utils.config.load_runtime_env_overrides",
            return_value={"POS_UNIFORMES_DB_HOST": "archivo"},
        ), patch.dict("os.environ", {"POS_UNIFORMES_DB_HOST": "entorno"}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.db_host, "entorno")


if __name__ == "__main__":
    unittest.main()
