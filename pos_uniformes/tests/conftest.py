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


# ---------------------------------------------------------------------------
# Ningun test levanta hilos de Postgres ni se queda esperando un clic.
#
# Las ventanas (MainWindow, QuoteSatelliteWindow) hacen trabajo real en su
# __init__: arrancan hilos QThread con LISTEN de Postgres y, si algo falla,
# abren un QMessageBox modal. Bajo test eso daba tres sintomas distintos con
# una sola causa:
#
#   - CUELGUE: QMessageBox.critical esperando un clic que nunca llega. La base
#     de prueba esta vacia, _load_operator_context revienta, y la corrida se
#     queda ahi para siempre (se vieron procesos colgados 19 horas).
#   - ABORT:   un QMessageBox sin QApplication → qFatal.
#   - SEGFAULT: el GC corriendo mientras un hilo psycopg sigue bloqueado en
#     notifies(); los hilos nunca se detienen entre tests y se acumulan.
#
# Esto NO arregla el diseño — eso es sacar el trabajo pesado del __init__. Es
# la red que permite volver a correr y medir la suite sin tocar produccion.
# ---------------------------------------------------------------------------

_LISTENERS = (
    ("pos_uniformes.ui.helpers.anuncio_listener", "AnuncioNotifyListener"),
    ("pos_uniformes.ui.helpers.trabajo_listener", "TrabajoNotifyListener"),
)

# Dialogos que solo informan: su valor de retorno no decide nada, unicamente
# bloquean. `question` NO se toca a proposito — ahi la respuesta cambia el flujo
# y debe elegirla cada test.
_DIALOGOS_BLOQUEANTES = ("information", "warning", "critical", "about")


@pytest.fixture(autouse=True)
def _sin_hilos_ni_dialogos_modales(monkeypatch: pytest.MonkeyPatch) -> None:
    if "PyQt6.QtCore" not in sys.modules:
        # Test rapido: no hay Qt cargado, no hay nada que neutralizar (y no
        # queremos importarlo justo aqui, que es lo que cuesta tiempo).
        return

    import importlib

    for nombre_modulo, nombre_clase in _LISTENERS:
        try:
            modulo = importlib.import_module(nombre_modulo)
        except Exception:  # noqa: BLE001 — si no se puede importar, no aplica
            continue
        clase = getattr(modulo, nombre_clase, None)
        if clase is None:
            continue
        monkeypatch.setattr(clase, "start", lambda self, *a, **k: None, raising=False)
        monkeypatch.setattr(clase, "run", lambda self, *a, **k: None, raising=False)

    # El satelite ademas lanza un `threading.Thread` (no QThread) desde su
    # __init__ via refresh_all: el watchdog de la base. Ese hilo sobrevive al
    # test, y cuando otro test parchea `get_session` o cuenta llamadas, el
    # hilo huerfano se mete y lo hace fallar de forma intermitente (se vio en
    # test_quote_satellite_offline_guards y test_search_input_helper).
    #
    # Se apaga SOLO durante la construccion: los tests del watchdog llaman
    # `_start_background_db_refresh` a mano despues, y ese si debe ser el real.
    try:
        from pos_uniformes.ui import quote_satellite_window as _qsw
    except Exception:  # noqa: BLE001
        _qsw = None
    if _qsw is not None:
        _init_real = _qsw.QuoteSatelliteWindow.__init__

        def _init_sin_watchdog(self, *args, **kwargs):
            self._start_background_db_refresh = lambda: None
            try:
                _init_real(self, *args, **kwargs)
            finally:
                # De vuelta al metodo de la clase para lo que venga despues.
                self.__dict__.pop("_start_background_db_refresh", None)

        monkeypatch.setattr(_qsw.QuoteSatelliteWindow, "__init__", _init_sin_watchdog)

    from PyQt6.QtWidgets import QMessageBox

    for nombre in _DIALOGOS_BLOQUEANTES:
        monkeypatch.setattr(
            QMessageBox,
            nombre,
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok),
            raising=False,
        )


# ---------------------------------------------------------------------------
# Semilla minima de la base de prueba.
#
# Las ventanas resuelven su operador con `user_id=1` en el __init__. Contra la
# base de prueba vacia eso reventaba con "Usuario no encontrado." — 53 fallos
# de un solo origen. No es un bug de la app: es que la base limpia no trae con
# que arrancar.
#
# Se siembra lo minimo y solo si falta. Es idempotente, asi que no estorba si
# la base ya tiene datos.
# ---------------------------------------------------------------------------

_USUARIO_DE_PRUEBA_ID = 1


@pytest.fixture(scope="session", autouse=True)
def _usuario_de_prueba() -> None:
    if "PyQt6.QtCore" not in sys.modules and "sqlalchemy" not in sys.modules:
        return  # test rapido: no hay base de por medio

    try:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.database.models import RolUsuario, Usuario
    except Exception:  # noqa: BLE001 — sin base disponible no hay nada que sembrar
        return

    try:
        with get_session() as session:
            existente = session.get(Usuario, _USUARIO_DE_PRUEBA_ID)
            if existente is not None:
                return
            session.add(
                Usuario(
                    id=_USUARIO_DE_PRUEBA_ID,
                    username="test_admin",
                    nombre_completo="Admin de pruebas",
                    password_hash="x",  # no se autentica: solo se resuelve el operador
                    rol=RolUsuario.ADMIN,
                    activo=True,
                )
            )
            session.commit()
    except Exception:  # noqa: BLE001 — que la falta de base no tumbe la colecta
        return
