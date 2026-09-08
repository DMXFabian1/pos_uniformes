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
from pathlib import Path
import re

import pytest

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
