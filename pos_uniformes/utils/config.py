"""Configuracion de entorno para la aplicacion local."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_echo: bool
    auto_create_schema: bool

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_host=os.getenv("POS_UNIFORMES_DB_HOST", "localhost"),
            db_port=int(os.getenv("POS_UNIFORMES_DB_PORT", "5432")),
            db_name=os.getenv("POS_UNIFORMES_DB_NAME", "pos_uniformes"),
            db_user=os.getenv("POS_UNIFORMES_DB_USER", "postgres"),
            db_password=os.getenv("POS_UNIFORMES_DB_PASSWORD", "postgres"),
            db_echo=_to_bool(os.getenv("POS_UNIFORMES_DB_ECHO"), default=False),
            auto_create_schema=_to_bool(os.getenv("POS_UNIFORMES_AUTO_CREATE_SCHEMA"), default=False),
        )


settings = Settings.from_env()
