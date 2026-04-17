"""Configuracion de entorno para la aplicacion local."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _appdata_config_dir() -> Path | None:
    """Carpeta de config persistente en AppData (solo cuando corre como bundle)."""
    if not getattr(sys, "frozen", False):
        return None
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "PresupuestosSatelite"


def satellite_data_dir() -> Path:
    """Carpeta de datos del satélite donde vive favorites.json.

    Bundle  → %APPDATA%\\PresupuestosSatelite\\
    Dev/Mac → junto al código fuente
    """
    appdata_dir = _appdata_config_dir()
    if appdata_dir is not None:
        return appdata_dir
    return runtime_base_dir()


def load_runtime_env_overrides(base_dir: Path | None = None) -> dict[str, str]:
    root = (base_dir or runtime_base_dir()).resolve()
    overrides: dict[str, str] = {}
    for candidate_name in ("pos_uniformes.env", ".env"):
        candidate = root / candidate_name
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            normalized_key = key.strip()
            if not normalized_key:
                continue
            normalized_value = value.strip().strip('"').strip("'")
            overrides.setdefault(normalized_key, normalized_value)
    return overrides


@dataclass
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_echo: bool
    auto_create_schema: bool
    backup_external_dir: str | None
    # API movil
    api_secret_key: str
    api_host: str
    api_port: int
    api_token_expire_hours: int

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @classmethod
    def from_env(cls) -> "Settings":
        file_overrides = load_runtime_env_overrides()

        def env_value(name: str, default: str) -> str:
            return os.getenv(name, file_overrides.get(name, default))

        def optional_env_value(name: str) -> str | None:
            raw_value = os.getenv(name, file_overrides.get(name))
            if raw_value is None:
                return None
            normalized_value = raw_value.strip()
            return normalized_value or None

        return cls(
            db_host=env_value("POS_UNIFORMES_DB_HOST", "localhost"),
            db_port=int(env_value("POS_UNIFORMES_DB_PORT", "5432")),
            db_name=env_value("POS_UNIFORMES_DB_NAME", "pos_uniformes"),
            db_user=env_value("POS_UNIFORMES_DB_USER", "postgres"),
            db_password=env_value("POS_UNIFORMES_DB_PASSWORD", "postgres"),
            db_echo=_to_bool(os.getenv("POS_UNIFORMES_DB_ECHO", file_overrides.get("POS_UNIFORMES_DB_ECHO")), default=False),
            auto_create_schema=_to_bool(
                os.getenv(
                    "POS_UNIFORMES_AUTO_CREATE_SCHEMA",
                    file_overrides.get("POS_UNIFORMES_AUTO_CREATE_SCHEMA"),
                ),
                default=False,
            ),
            backup_external_dir=optional_env_value("POS_UNIFORMES_BACKUP_EXTERNAL_DIR"),
            api_secret_key=env_value("POS_API_SECRET_KEY", "cambiar-esta-clave-en-produccion"),
            api_host=env_value("POS_API_HOST", "0.0.0.0"),
            api_port=int(env_value("POS_API_PORT", "8000")),
            api_token_expire_hours=int(env_value("POS_API_TOKEN_EXPIRE_HOURS", "8")),
        )


settings = Settings.from_env()
