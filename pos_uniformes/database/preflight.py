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
    # True cuando la base tiene una revisión que este programa NI SIQUIERA
    # conoce: la principal migró con código más nuevo que el de este programa.
    # Aquí no se arranca (no se sabe qué cambió), pero el atrasado es el
    # programa, no la base (Kiosko Principal, 2026-11-13).
    programa_viejo: bool = False

    @property
    def is_up_to_date(self) -> bool:
        return self.current_heads == self.expected_heads


TITULO_BASE_NO_LISTA = "Base de datos no lista"
TITULO_PROGRAMA_VIEJO = "Programa desactualizado"


class DatabasePreflightError(RuntimeError):
    """Se lanza cuando la app no puede arrancar con la base actual.

    `titulo` es lo que va en la barra del aviso: «Base de datos no lista» o,
    si el viejo es el programa, «Programa desactualizado»."""

    def __init__(self, mensaje: str, *, titulo: str = TITULO_BASE_NO_LISTA, programa_viejo: bool = False) -> None:
        super().__init__(mensaje)
        self.titulo = titulo
        self.programa_viejo = programa_viejo


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


# Cómo está la base contra lo que pide este programa (cuando no son iguales).
BASE_ADELANTE = "adelante"          # la base es descendiente de lo que pide: arranca con aviso
BASE_DESCONOCIDA = "desconocida"    # la base tiene una revisión que este programa no conoce
BASE_ATRASADA = "atrasada"          # le falta algo que el programa pide: alembic upgrade


def _relacion_base(script, current_heads: tuple[str, ...], expected_heads: tuple[str, ...]) -> str:
    """Compara las cabezas de la base con las del programa usando `script`
    (un `ScriptDirectory`, o uno simulado en las pruebas).

    Si alguna cabeza de la base no existe en las migraciones de este
    programa, el viejo es el programa: la principal migró con código más
    nuevo. Antes eso caía en «base desactualizada», que es al revés."""
    if not current_heads:
        return BASE_ATRASADA
    adelante = True
    for actual in current_heads:
        try:
            revision = script.get_revision(actual)
        except Exception:  # noqa: BLE001 — alembic: «Can't locate revision»
            revision = None
        if revision is None:
            return BASE_DESCONOCIDA
        try:
            historia = {r.revision for r in script.iterate_revisions(revision.revision, "base")}
        except Exception:  # noqa: BLE001 — ante la duda, se trata como desactualizada
            return BASE_ATRASADA
        if not set(expected_heads) <= historia:
            adelante = False
    return BASE_ADELANTE if adelante else BASE_ATRASADA


def _base_va_adelante(config: Config, current_heads: tuple[str, ...], expected_heads: tuple[str, ...]) -> bool:
    """¿La versión de la base es descendiente de la que pide este programa?
    Entonces el atrasado es el programa, no la base."""
    try:
        script = ScriptDirectory.from_config(config)
    except Exception:  # noqa: BLE001
        return False
    return _relacion_base(script, current_heads, expected_heads) == BASE_ADELANTE


def _version_del_programa() -> str:
    """«13 nov · 9fe9d71d» (o lo que haya); nunca tumba el aviso."""
    try:
        from pos_uniformes.utils.app_metadata import version_visible

        return version_visible() or "desconocida"
    except Exception:  # noqa: BLE001
        return "desconocida"


def mensaje_programa_viejo(current: str, expected: str) -> str:
    """El aviso cuando el viejo es el programa. Sin hint de alembic: migrar
    no arregla nada, lo que hay que hacer es actualizar el programa."""
    return (
        "Este programa es más viejo que la base de datos: la base ya tiene cambios que esta "
        "versión no conoce.\n\n"
        "En un kiosko: cierra y vuelve a abrir el acceso directo para que se actualice solo; "
        "si sigue igual, corre reparar_satelite.bat.\n"
        "En la PC principal: corre actualizar_pc_principal.bat.\n\n"
        f"Versión del programa: {_version_del_programa()} (conoce la base hasta {expected})\n"
        f"Versión de la base: {current}"
    )


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

    relacion = BASE_ATRASADA
    if current_heads != expected_heads:
        relacion = _relacion_base(script, current_heads, expected_heads)
    return DatabasePreflightStatus(
        current_heads=current_heads,
        expected_heads=expected_heads,
        base_adelante=relacion == BASE_ADELANTE,
        programa_viejo=relacion == BASE_DESCONOCIDA,
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
    if status.programa_viejo:
        # La base tiene una revisión que este programa no conoce: no se sabe
        # qué cambió, así que NO arranca. Pero se dice la verdad: el viejo es
        # el programa, y se arregla actualizándolo, no con alembic.
        raise DatabasePreflightError(
            mensaje_programa_viejo(current, expected),
            titulo=TITULO_PROGRAMA_VIEJO,
            programa_viejo=True,
        )
    raise DatabasePreflightError(
        "La base de datos esta desactualizada para esta version del programa.\n\n"
        f"Version actual: {current}\n"
        f"Version esperada: {expected}\n\n"
        f"{_upgrade_hint()}"
    )
