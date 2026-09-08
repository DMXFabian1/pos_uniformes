"""Clasificacion automatica de tests: `db` (PostgreSQL real) y `qt` (PyQt6).

Objetivo: que el ciclo de trabajo diario sea rapido. Los tests que necesitan
base de datos o Qt son los lentos y los fragiles fuera de la tienda, asi que
se marcan solos y se pueden saltar con `--fast`.

No hay que decorar ningun test a mano: la clasificacion se hace leyendo el
codigo fuente de cada archivo, SIN importarlo. Eso importa, porque importar un
modulo de Qt ya cuesta tiempo — con `--fast` esos archivos ni siquiera se
recolectan.

    pytest pos_uniformes/tests --fast      # ciclo diario
    pytest pos_uniformes/tests             # todo, antes de produccion
    pytest pos_uniformes/tests -m db       # solo los de base
"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import re
import sys

import pytest

# ---------------------------------------------------------------------------
# Aislamiento de la base de datos — NINGUN test toca produccion.
#
# Los tests leian la config normal de la app, o sea el `pos_uniformes.env` de
# esta maquina. En la Mac eso apunta a 192.168.0.10/pos_uniformes: la base REAL
# de la tienda. Un test llego a encolar un trabajo de impresion de verdad.
#
# Esto se fija aqui, al importar conftest, porque `utils.config.settings` es un
# singleton que se arma en el import del modulo: si esperamos a un hook de
# pytest ya es tarde. Por eso tambien se lee `sys.argv` a mano — las opciones
# de pytest todavia no estan parseadas en este punto.
#
# Escotilla de salida para correr contra una base real (en la tienda):
#     pytest pos_uniformes/tests --db-real
# ---------------------------------------------------------------------------

_TEST_DB_HOST = "127.0.0.1"
_TEST_DB_NAME = "pos_uniformes_test"
_USA_BASE_REAL = "--db-real" in sys.argv

if not _USA_BASE_REAL:
    os.environ["POS_UNIFORMES_DB_HOST"] = _TEST_DB_HOST
    os.environ["POS_UNIFORMES_DB_NAME"] = _TEST_DB_NAME
    # Nunca crear esquema solo por correr tests: la base de prueba se prepara
    # aparte con `alembic upgrade head`.
    os.environ["POS_UNIFORMES_AUTO_CREATE_SCHEMA"] = "0"

# Señales de que un archivo de test necesita cada dependencia.
# `pos_uniformes.ui` importa PyQt6 en cadena: un test que lo toca es un test Qt
# aunque nunca escriba "PyQt6".
_QT_PATTERN = re.compile(
    r"\b(?:PyQt6|QApplication|QtWidgets|QtCore|qtbot)\b|pos_uniformes\.ui\b"
)
_DB_PATTERN = re.compile(
    r"\b(?:get_session|create_engine|init_db|sessionmaker|database\.connection)\b"
)


@lru_cache(maxsize=None)
def _classify(path_str: str) -> frozenset[str]:
    """Devuelve los markers que le tocan a un archivo de test.

    Lee el fuente en vez de importarlo: la clasificacion no debe pagar el costo
    que justamente queremos evitar.
    """
    try:
        source = Path(path_str).read_text(encoding="utf-8", errors="replace")
    except OSError:
        # Si no se puede leer, no clasificamos: que corra como test normal.
        return frozenset()

    markers = set()
    if _QT_PATTERN.search(source):
        markers.add("qt")
    if _DB_PATTERN.search(source):
        markers.add("db")
    return frozenset(markers)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--fast",
        action="store_true",
        default=False,
        help="Solo tests rapidos: omite los que necesitan PostgreSQL o Qt.",
    )
    parser.addoption(
        "--db-real",
        action="store_true",
        default=False,
        help=(
            "Correr contra la base configurada en el .env en vez de la de "
            "prueba local. Solo para diagnostico; puede escribir en produccion."
        ),
    )


def pytest_configure(config: pytest.Config) -> None:
    """Ultima red: si apuntamos a algo que huele a produccion, no corremos."""
    if config.getoption("--db-real"):
        return

    from pos_uniformes.utils.config import settings

    host = (settings.db_host or "").strip()
    nombre = (settings.db_name or "").strip()
    es_local = host in {"127.0.0.1", "localhost", "::1"}

    if not es_local or not nombre.endswith("_test"):
        raise pytest.UsageError(
            "Los tests quedaron apuntando a una base que no es de prueba "
            f"({host}/{nombre}). Se aborta para no tocar produccion.\n"
            "Si de verdad quieres correr contra esa base, usa --db-real."
        )


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Con `--fast`, ni siquiera importamos los archivos lentos."""
    if not config.getoption("--fast"):
        return None
    if collection_path.suffix != ".py" or not collection_path.name.startswith("test_"):
        return None
    if _classify(str(collection_path)):
        return True
    return None


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Aplica los markers `db`/`qt` para que `-m` funcione sin decorar nada."""
    for item in items:
        for marker in _classify(str(item.path)):
            item.add_marker(getattr(pytest.mark, marker))
