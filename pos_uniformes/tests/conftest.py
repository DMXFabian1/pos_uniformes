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

from tests import base_por_trabajador as _bpt

_TEST_DB_HOST = "127.0.0.1"
_USA_BASE_REAL = "--db-real" in sys.argv
# Con xdist, cada proceso usa su propia copia de `pos_uniformes_test` (ver
# tests/base_por_trabajador.py): las pruebas que suman una tabla entera ya no
# ven lo que otro proceso escribió. Sin xdist es `pos_uniformes_test`.
_TEST_DB_NAME = _bpt.base_para_este_proceso()

if not _USA_BASE_REAL:
    os.environ["POS_UNIFORMES_DB_HOST"] = _TEST_DB_HOST
    os.environ["POS_UNIFORMES_DB_NAME"] = _TEST_DB_NAME
    # Nunca crear esquema solo por correr tests: la base de prueba se prepara
    # aparte con `alembic upgrade head`.
    os.environ["POS_UNIFORMES_AUTO_CREATE_SCHEMA"] = "0"

# Lo que dice el .env de la máquina sobre SÍ MISMA no aplica a los tests: en la
# Mac de desarrollo los satélites de prueba dejaban de latir (2026-10-11).
os.environ["POS_UNIFORMES_SATELITE_DESARROLLO"] = "0"

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


_VENTANAS_SATELITE: list = []


def conservar_hasta_el_final(widget) -> None:
    """Cerrar un widget sin destruirlo hasta que termine la sesión.

    El kiosko deja temporizadores sin dueño Qt: `_flash_scan_hint` programa
    `QTimer.singleShot(1800, lambda: self._scan_hint.setText(...))`. Si una
    prueba lo borra con `deleteLater` antes de los 1.8 s, la lambda cae sobre la
    etiqueta ya destruida en la siguiente prueba que corra el ciclo de eventos,
    y PyQt6 tumba el proceso (RuntimeError en un slot → Fatal: Aborted). Se vio
    1 de cada 4-5 corridas completas con -n 6 (2026-11-11). Igual que las
    ventanas satélite: se cierra ya, se libera al final.
    """
    widget.close()
    _VENTANAS_SATELITE.append(widget)


def pytest_sessionfinish(session, exitstatus) -> None:
    """Cierra las ventanas satelite que los tests dejaron vivas, con Qt aun
    despierto, para que no las mate el recolector a destiempo."""
    if not _VENTANAS_SATELITE:
        return
    try:
        from unittest.mock import patch

        from PyQt6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        # Al procesar los eventos puede saltar un aviso diferido de la ventana
        # (p. ej. «Falta elegir la impresora de tickets», a los 1.5 s). Un
        # QMessageBox modal con Qt cerrándose tumbaba el proceso con «Fatal
        # Python error: Aborted»; aquí los avisos no se muestran.
        with patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "information"), \
             patch.object(QMessageBox, "critical"), patch.object(QMessageBox, "question"):
            for w in _VENTANAS_SATELITE:
                try:
                    w.close()
                    w.deleteLater()
                except Exception:  # noqa: BLE001
                    pass
            if app is not None:
                app.processEvents()
    except Exception:  # noqa: BLE001
        pass
    _VENTANAS_SATELITE.clear()


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

    _preparar_base_por_proceso(config, settings)


def _corre_con_trabajadores(config: pytest.Config) -> bool:
    """¿Este es el controlador de una corrida con xdist?"""
    if hasattr(config, "workerinput"):
        return False
    if not config.pluginmanager.hasplugin("xdist"):
        return False
    numero = getattr(config.option, "numprocesses", None)
    return bool(numero) and getattr(config.option, "dist", "no") != "no"


def _preparar_base_por_proceso(config: pytest.Config, settings) -> None:
    corrida = os.environ[_bpt.ENV_CORRIDA]
    url = settings.database_url
    if hasattr(config, "workerinput"):
        nombre = settings.db_name
        if not _bpt.es_temporal_de_prueba(nombre):
            return
        try:
            _bpt.crear_desde(url, nombre, _bpt.nombre_plantilla(corrida))
        except Exception as exc:  # noqa: BLE001
            raise pytest.UsageError(f"No se pudo crear la base de este proceso ({nombre}): {exc}") from exc
        config._base_por_proceso = nombre
    elif _corre_con_trabajadores(config):
        plantilla = _bpt.nombre_plantilla(corrida)
        try:
            _bpt.limpiar(url)  # lo viejo de corridas que alguien mató
            _bpt.crear_desde(url, plantilla, _bpt.BASE_FUENTE)
        except Exception as exc:  # noqa: BLE001
            raise pytest.UsageError(
                f"No se pudo copiar {_bpt.BASE_FUENTE} para esta corrida: {exc}"
            ) from exc
        config._plantilla_de_corrida = plantilla


def pytest_unconfigure(config: pytest.Config) -> None:
    """Cada proceso borra su base; el controlador, la plantilla y lo que sobre."""
    from pos_uniformes.utils.config import settings

    nombre = getattr(config, "_base_por_proceso", None)
    if nombre:
        try:
            from pos_uniformes.database.connection import engine

            engine.dispose()
        except Exception:  # noqa: BLE001
            pass
        try:
            _bpt.borrar(settings.database_url, nombre)
        except Exception:  # noqa: BLE001 — la limpia del controlador la alcanza
            pass
    if getattr(config, "_plantilla_de_corrida", None):
        try:
            _bpt.limpiar(settings.database_url, corrida=os.environ[_bpt.ENV_CORRIDA])
        except Exception:  # noqa: BLE001 — la siguiente corrida la borra por vieja
            pass


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
            # Muchos tests crean la ventana y la sueltan sin cerrarla. Si el
            # recolector de basura la alcanza a media prueba (cualquier prueba,
            # en el mismo worker), Qt todavia la tiene instalada como filtro de
            # eventos y el proceso muere con "Segmentation fault ... eventFilter".
            # Se guarda una referencia viva y se cierran todas al final.
            _VENTANAS_SATELITE.append(self)

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
# Cada prueba cierra los dialogos que abre (2026-11-11).
#
# Un dialogo que una prueba dejaba visible (el conteo fisico, el detalle del
# dia de una empleada, el aviso de la Libreta) seguia vivo en ese proceso y la
# prueba de higiene de otra seccion (`activeModalWidget() is None`) fallaba
# segun el orden en que xdist repartia las pruebas.
#
# Esto NO los esconde: si una prueba deja un dialogo nuevo a la vista, se
# cierra (para que la siguiente arranque limpia) y la prueba que lo dejo
# FALLA con el nombre del dialogo. La higiene sigue viendo todo lo demas.
# ---------------------------------------------------------------------------


def _dialogos_visibles() -> dict:
    if "PyQt6.QtWidgets" not in sys.modules:
        return {}
    from PyQt6 import sip
    from PyQt6.QtWidgets import QApplication, QDialog

    if QApplication.instance() is None:
        return {}
    visibles = {}
    for w in QApplication.topLevelWidgets():
        try:
            if isinstance(w, QDialog) and w.isVisible():
                visibles[int(sip.unwrapinstance(w))] = w
        except RuntimeError:  # ya destruido del lado de C++
            continue
    return visibles


def _describir_dialogo(w) -> str:
    try:
        return f"{type(w).__name__} «{w.windowTitle() or w.objectName() or 'sin título'}»"
    except RuntimeError:
        return type(w).__name__


def cerrar_dialogos(dialogos) -> None:
    """Cierra de verdad: `done` oculta aunque el dialogo ignore el close
    (un QMessageBox sin boton de escape lo ignora)."""
    for w in dialogos:
        try:
            w.done(0)
            if w.isVisible():
                w.hide()
            w.deleteLater()
        except RuntimeError:
            continue


@pytest.fixture(autouse=True)
def _cada_prueba_cierra_sus_dialogos(request):
    antes = set(_dialogos_visibles())
    yield
    nuevos = {k: w for k, w in _dialogos_visibles().items() if k not in antes}
    if not nuevos:
        return
    nombres = ", ".join(sorted(_describir_dialogo(w) for w in nuevos.values()))
    cerrar_dialogos(nuevos.values())
    pytest.fail(
        f"{request.node.nodeid} dejó abierto: {nombres}. "
        "Cada prueba cierra los diálogos que abre.",
        pytrace=False,
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


# La copia local de nombres (data/empleadas_nombres.json) va a un temporal
# durante TODA la vida del proceso de pruebas: hay hilos de fondo del satélite
# que sobreviven a cualquier fixture y escribirían en data/ del repo.
def _desviar_copia_local_de_nombres() -> None:
    import atexit
    import tempfile
    from pathlib import Path

    from pos_uniformes.services import nombres_empleadas_service as ne

    d = tempfile.mkdtemp(prefix="nombres_empleadas_")
    ne._ruta_local = lambda: Path(d) / "nombres.json"
    atexit.register(lambda: __import__("shutil").rmtree(d, ignore_errors=True))


_desviar_copia_local_de_nombres()


# La identidad de la PC (nombre e id) y lo leído del buzón también van a un
# temporal: una prueba de renombrar le cambió el nombre a la Mac de verdad
# (quedó «Entrada», 2026-10-15). Las pruebas que necesitan su propia carpeta
# la parchan encima, y al terminar vuelve a este temporal, nunca a data/.
def _desviar_identidad_y_buzon() -> None:
    import atexit
    import tempfile
    from pathlib import Path

    from pos_uniformes.services import buzon_service as bz
    from pos_uniformes.services import satellite_identity_service as ident

    from pos_uniformes.services import telegram_limpieza_service as limpieza

    d = Path(tempfile.mkdtemp(prefix="identidad_pc_"))
    ident.satellite_data_dir = lambda: d
    bz._ruta_leidos = lambda: d / "buzon_leidos.json"
    # La lista de mensajes del bot: el ciclo de escucha la escribía en data/.
    limpieza.ruta_estado = lambda: d / "bot_mensajes.json"
    atexit.register(lambda: __import__("shutil").rmtree(d, ignore_errors=True))


_desviar_identidad_y_buzon()


@pytest.fixture(autouse=True)
def _nombres_empleadas_limpios():
    """La caché de nombres (VEND-1 → Daniel) es global: cada test arranca sin ella."""
    from pos_uniformes.services import nombres_empleadas_service as ne

    ne._cache, ne._cache_en = {}, 0.0
    yield
    ne._cache, ne._cache_en = {}, 0.0


@pytest.fixture(autouse=True)
def _vigilante_sin_memoria_de_esta_maquina(tmp_path):
    """Lo que el vigilante del bot ya avisó hoy vive en disco (2026-10-10):
    un test no debe leer lo que otro, o la máquina, dejó anotado."""
    from unittest.mock import patch

    from pos_uniformes.services import alertas_service as al

    from pos_uniformes.services import telegram_bot_service as tbs

    from pos_uniformes.services import telegram_corte_botones_service as tcb

    from pos_uniformes.scripts import resumen_diario_telegram as rdt

    # La revisión «el resumen no salió» se apaga: cualquier prueba del
    # vigilante que corra con la hora real después de las 19:25 recibía un
    # aviso de más (vigilancia, 2026-11-07). test_vigilancia_noviembre la
    # prueba llamando a la original.
    with patch.object(al, "ruta_memoria", lambda: tmp_path / "bot_vigilante.json"), \
         patch.object(tbs, "ruta_offset", lambda: tmp_path / "bot_offset.json"), \
         patch.object(tcb, "ruta_notas", lambda: tmp_path / "corte_notas_pendientes.json"), \
         patch.object(rdt, "ruta_resumen_enviado", lambda: tmp_path / "resumen_enviado.json"), \
         patch.object(al.Vigilante, "_resumen_que_no_salio", lambda self, session, ahora: []):
        yield


#: Archivos de la máquina que las pruebas NO deben tocar (auditoría C1,
#: 2026-11-08: una corrida completa reescribía `data/` real del repo, incluido
#: el estado del bot). (módulo, función que devuelve la ruta).
_RUTAS_DE_LA_MAQUINA = (
    # respaldo de operaciones cobradas sin anotar y cola de la Libreta
    ("pos_uniformes.services.libreta_sin_anotar_service", "carpeta"),
    ("pos_uniformes.services.libreta_local_queue_service", "_queue_path"),
    ("pos_uniformes.services.libreta_local_queue_service", "_cortes_path"),
    # cachés del kiosko (los escriben hilos de fondo de las ventanas)
    ("pos_uniformes.services.catalog_local_cache_service", "_cache_path"),
    ("pos_uniformes.services.school_links_cache_service", "_links_cache_path"),
    ("pos_uniformes.services.anuncio_local_cache_service", "_dir"),
    ("pos_uniformes.services.business_info_cache_service", "_cache_path"),
    # estado del bot y log de errores del satélite
    ("pos_uniformes.services.bot_conexion_service", "ruta_estado"),
    ("pos_uniformes.utils.satellite_excepthook", "_log_path"),
    ("pos_uniformes.services.temporada_service", "ruta_bitacora"),
)


@pytest.fixture(scope="session", autouse=True)
def _datos_de_la_maquina_fuera_del_alcance(tmp_path_factory):
    """Ninguna prueba escribe en `pos_uniformes/data` ni `pos_uniformes/logs`
    del repo (ahí viven el estado real del bot, los cachés y los respaldos de
    esta máquina).

    Cada función de ruta se envuelve: si la ruta que devuelve cae DENTRO de
    esas carpetas, se desvía a una carpeta temporal de la sesión; si no (la
    prueba ya desvió `satellite_data_dir` a su propia carpeta), se respeta.
    Así quien prueba un caché con su carpeta temporal sigue igual.

    Es de SESIÓN y no por prueba porque varios de esos archivos los escriben
    hilos de fondo que terminan cuando la prueba que los lanzó ya acabó.
    Solo existe en pytest: el kiosko y el POS no cargan conftest."""
    import importlib
    from unittest.mock import patch

    raiz = Path(__file__).resolve().parents[1]
    protegidas = [(raiz / "data").resolve(), (raiz / "logs").resolve()]
    destino_base = tmp_path_factory.mktemp("datos_de_la_maquina")

    def envolver(funcion):
        def ruta(*args, **kwargs):
            destino = Path(funcion(*args, **kwargs))
            for carpeta in protegidas:
                try:
                    relativa = destino.resolve().relative_to(carpeta)
                except ValueError:
                    continue
                return destino_base / carpeta.name / relativa
            return destino

        ruta.__wrapped__ = funcion
        return ruta

    parches = []
    for nombre_modulo, atributo in _RUTAS_DE_LA_MAQUINA:
        modulo = importlib.import_module(nombre_modulo)
        parches.append(patch.object(modulo, atributo, envolver(getattr(modulo, atributo))))
    for p in parches:
        p.start()
    # A propósito NO se retiran al terminar la sesión: al salir el proceso de
    # pruebas, temporizadores e hilos de ventanas que sobrevivieron siguen
    # corriendo un momento y escribían el índice de anuncios y la bitácora
    # de temporada en el repo. El desvío dura hasta que el proceso muere.
    yield destino_base


#: Estado de la Libreta que NO se comparte entre pruebas: un respaldo
#: «cobrado sin anotar» que deja una prueba lo recuperaría la ventana de la
#: siguiente (y al cerrarla preguntaría por él).
_RUTAS_POR_PRUEBA = (
    ("pos_uniformes.services.libreta_sin_anotar_service", "carpeta"),
    ("pos_uniformes.services.libreta_local_queue_service", "_queue_path"),
    ("pos_uniformes.services.libreta_local_queue_service", "_cortes_path"),
)


@pytest.fixture(autouse=True)
def _libreta_de_cada_prueba(tmp_path, _datos_de_la_maquina_fuera_del_alcance):
    """Encima del desvío de sesión: la cola y los respaldos de la Libreta que
    caerían en el repo van a la carpeta temporal de ESTA prueba."""
    import importlib
    from unittest.mock import patch

    raiz = Path(__file__).resolve().parents[1]
    datos = (raiz / "data").resolve()

    def envolver(actual):
        original = getattr(actual, "__wrapped__", actual)

        def ruta(*args, **kwargs):
            destino = Path(original(*args, **kwargs))
            try:
                relativa = destino.resolve().relative_to(datos)
            except ValueError:
                return destino
            return tmp_path / "libreta_aislada" / relativa

        ruta.__wrapped__ = original
        return ruta

    parches = [
        patch.object(m, a, envolver(getattr(m, a)))
        for m, a in ((importlib.import_module(n), a) for n, a in _RUTAS_POR_PRUEBA)
    ]
    for p in parches:
        p.start()
    try:
        yield
    finally:
        for p in reversed(parches):
            p.stop()


@pytest.fixture(autouse=True)
def _temporada_sin_ajuste_de_esta_maquina(tmp_path):
    """Los tests ven el calendario, no lo que esta máquina tenga configurado.

    En cuanto las temporadas se pudieron fijar desde el menú (07/10), la Mac de
    Daniel quedó en «Siempre: Halloween» y 11 tests del calendario empezaron a
    fallar: estaban leyendo un archivo de la máquina. Un test que depende de
    cómo quedó configurada la computadora no prueba nada.

    Se aísla el ARCHIVO y no la función: así quien prueba el ajuste mismo
    sigue pudiendo guardarlo y leerlo de vuelta, solo que en su propia carpeta.
    Lo mismo con la temporada forzada, que también deja archivo.

    Y desde que la temporada vive en la BASE (2026-10-09), también se aísla
    esa lectura: un test que guardaba «Halloween» se lo dejaba puesto a toda
    la base de pruebas y los siguientes veían una temporada que no habían
    pedido. Quien prueba el camino de la base lo parchea a mano.
    """
    from unittest.mock import patch

    from pos_uniformes.services import temporada_service as temp

    temp.olvidar_lo_leido()
    with patch.object(temp, "ruta_ajuste", lambda: tmp_path / "temporada_ajuste.json"), \
         patch.object(temp, "ruta_forzada", lambda: tmp_path / "temporada_forzada.json"), \
         patch.object(temp, "ruta_fechas", lambda: tmp_path / "temporada_fechas.json"), \
         patch.object(temp, "ruta_bitacora", lambda: tmp_path / "temporada_bitacora.jsonl"), \
         patch.object(temp, "_ajuste_de_la_tienda", return_value=None), \
         patch.object(temp, "_fechas_de_la_tienda", return_value=None):
        yield
    temp.olvidar_lo_leido()
