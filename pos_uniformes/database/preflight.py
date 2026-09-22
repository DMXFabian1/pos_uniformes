"""Chequeos de conexion y esquema antes de abrir la app."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.exc import SQLAlchemyError

from pos_uniformes.database.connection import engine
from pos_uniformes.utils.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatabasePreflightStatus:
    current_heads: tuple[str, ...]
    expected_heads: tuple[str, ...]
    # True cuando la base va ADELANTE de este programa (el kiosko se quedó con
    # una versión vieja y la principal ya migró). No es un error: las columnas
    # y tablas nuevas simplemente no se usan.
    base_adelante: bool = False

    @property
    def is_up_to_date(self) -> bool:
        return self.current_heads == self.expected_heads


class DatabasePreflightError(RuntimeError):
    """Se lanza cuando la app no puede arrancar con la base actual."""


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _base_va_adelante(config: Config, current_heads: tuple[str, ...], expected_heads: tuple[str, ...]) -> bool:
    """¿La versión de la base es descendiente de la que pide este programa?
    Entonces el atrasado es el programa, no la base."""
    try:
        script = ScriptDirectory.from_config(config)
        for actual in current_heads:
            revision = script.get_revision(actual)
            historia = {r.revision for r in script.iterate_revisions(revision.revision, "base")}
            if not set(expected_heads) <= historia:
                return False
        return bool(current_heads)
    except Exception:  # noqa: BLE001 — ante la duda, se trata como desactualizada
        return False


def _upgrade_hint() -> str:
    return (
        "Actualiza el esquema con `python -m alembic upgrade head` ejecutado dentro de la carpeta "
        f"`{_project_root()}`."
    )


def _build_alembic_config() -> Config:
    project_root = _project_root()
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def inspect_database_status() -> DatabasePreflightStatus:
    config = _build_alembic_config()
    script = ScriptDirectory.from_config(config)
    expected_heads = tuple(sorted(script.get_heads()))

    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_heads = tuple(sorted(context.get_current_heads()))
    except SQLAlchemyError as exc:
        raise DatabasePreflightError(
            "No fue posible conectar con PostgreSQL.\n\n"
            f"Detalle: {exc}"
        ) from exc

    if not current_heads:
        raise DatabasePreflightError(
            "La base de datos no tiene una version registrada de Alembic.\n\n"
            f"{_upgrade_hint()}"
        )

    return DatabasePreflightStatus(
        current_heads=current_heads,
        expected_heads=expected_heads,
        base_adelante=_base_va_adelante(config, current_heads, expected_heads),
    )


def assert_database_ready() -> DatabasePreflightStatus:
    status = inspect_database_status()
    if status.is_up_to_date:
        return status
    current = ", ".join(status.current_heads)
    expected = ", ".join(status.expected_heads)
    if status.base_adelante:
        # El kiosko se quedó con una versión vieja: la base ya tiene lo nuevo y
        # esta app no lo usa. Arranca igual (antes tiraba "base desactualizada",
        # que decía justo lo contrario y confundía — Daniel, 2026-09-22).
        logger.warning(
            "Este programa es mas viejo que la base (programa %s, base %s). "
            "Arranca igual; para tener lo nuevo hay que publicar el satelite desde la PC principal.",
            expected, current,
        )
        return status
    raise DatabasePreflightError(
        "La base de datos esta desactualizada para esta version del programa.\n\n"
        f"Version actual: {current}\n"
        f"Version esperada: {expected}\n\n"
        f"{_upgrade_hint()}"
    )
