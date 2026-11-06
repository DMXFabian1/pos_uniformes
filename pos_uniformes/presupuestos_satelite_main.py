"""Punto de entrada para la app satelite de Presupuestos."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pos_uniformes.utils.venv_bootstrap import ensure_local_venv_site_packages

ensure_local_venv_site_packages(Path(__file__))

from PyQt6.QtCore import QLockFile, QStandardPaths, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from pos_uniformes.database.connection import init_db
from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import RolUsuario
from pos_uniformes.database.models import Usuario
from pos_uniformes.database.preflight import DatabasePreflightError, assert_database_ready
from pos_uniformes.services.catalog_local_cache_service import load_catalog_cache
from pos_uniformes.services.satellite_startup_service import probe_database_host
from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow
from pos_uniformes.utils.config import settings
from pos_uniformes.utils.app_metadata import satellite_display_name, satellite_windows_icon_path
from pos_uniformes.utils.satellite_excepthook import install_satellite_excepthook


def _show_splash_message(splash, msg: str, app: QApplication, detalle: str = "", avance: float | None = None) -> None:
    """Lo que dice la pantalla de arranque: qué hace, qué pasa si no resulta y cuánto lleva."""
    splash.decir(msg, detalle, avance)
    app.processEvents()


def bootstrap_schema() -> None:
    if not settings.auto_create_schema:
        return
    try:
        init_db()
    except SQLAlchemyError as exc:
        print(f"No fue posible inicializar el esquema: {exc}", file=sys.stderr)


def resolve_satellite_operator_id() -> int:
    with get_session() as session:
        users = session.scalars(
            select(Usuario).where(
                Usuario.activo.is_(True),
                Usuario.rol.in_((RolUsuario.CAJERO, RolUsuario.ADMIN)),
            )
        ).all()

        if not users:
            raise RuntimeError("No hay usuarios activos con rol ADMIN o CAJERO para abrir la app satelite.")

        def sort_key(user: Usuario) -> tuple[int, str, int]:
            role_priority = 0 if user.rol == RolUsuario.CAJERO else 1
            return (role_priority, str(user.username).lower(), int(user.id))

        return int(sorted(users, key=sort_key)[0].id)


def _modo_servidor_de_impresion(app) -> int:
    """`--servidor-impresion`: despacha la cola SIN abrir el kiosko.

    En la tienda las impresoras de etiquetas cuelgan del kiosko, y el kiosko no
    tiene Python —el lanzador solo le baja este .exe—, así que el servicio del
    repo no se podía instalar ahí. Con esto el mismo ejecutable sirve de
    servidor de impresión con la pantalla apagada (Daniel, 2026-10-05).

    Va ANTES del candado de instancia única: este proceso y la ventana del
    kiosko pueden convivir en la misma PC, cada uno con el suyo.
    """
    import logging

    from pos_uniformes.ui.helpers.servidor_impresion_runner import (
        correr,
        es_servidor_de_impresion,
        tomar_candado,
    )
    from pos_uniformes.utils.config import satellite_data_dir

    destino = satellite_data_dir() / "logs" / "servidor_impresion.log"
    destino.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(destino, encoding="utf-8")],
    )
    log = logging.getLogger("servidor_impresion")

    forzar = "--forzar" in sys.argv
    drenar = "--drenar" in sys.argv
    es_servidor, origen = es_servidor_de_impresion()
    if not es_servidor and not forzar:
        # Una Estación no tiene impresoras: despachar desde ahí reclamaría los
        # trabajos de las demás para mandarlos a una impresora que no existe.
        log.warning(
            "Esta PC (%s) está marcada como «Estación», no como «Servidor de "
            "impresión». No arranco. Cámbialo en el menú admin → «Rol de "
            "impresión de esta PC».", origen,
        )
        return 2
    if not drenar and not tomar_candado():
        log.info("Ya hay un servidor de impresión corriendo en esta PC. No arranco otro.")
        return 0
    bootstrap_schema()
    return correr(app, drenar=drenar, origen=origen)


def main() -> int:
    # Una excepcion que escape de un slot no debe cerrar el kiosko.
    install_satellite_excepthook()
    app = QApplication(sys.argv)
    if "--servidor-impresion" in sys.argv:
        return _modo_servidor_de_impresion(app)
    app.setApplicationName(satellite_display_name())
    app.setOrganizationName("POSUniformes")
    from pos_uniformes.utils.qt_spanish import instalar_espanol_qt

    instalar_espanol_qt(app)  # Sí/No/Cancelar en vez de Yes/No/Cancel
    icon_path = satellite_windows_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    # ── Instancia única ───────────────────────────────────────────────
    lock_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)
    lock_file = QLockFile(str(Path(lock_dir) / "presupuestos_satelite.lock"))
    if not lock_file.tryLock(100):
        QMessageBox.information(
            None,
            "Ya está abierto",
            "Presupuestos Satélite ya está corriendo.\n\nBusca la ventana en la barra de tareas.",
        )
        return 0
    # El menu admin necesita soltar este candado antes de reiniciar la app
    # (os.execv) — si no, la instancia nueva muere con "Ya esta abierto".
    app._instance_lock = lock_file

    # ── Splash ────────────────────────────────────────────────────────
    from pos_uniformes.ui.helpers.satellite_splash import SplashDelKiosko
    from pos_uniformes.utils.app_metadata import version_visible

    splash = SplashDelKiosko(version_visible())
    splash.show()
    app.processEvents()

    # ── Arranque ──────────────────────────────────────────────────────
    # Meilisearch es LOCAL de esta PC: arranca solo (si está instalado) y
    # re-indexa en background — también cuando la PC principal está apagada.
    # Sin DB conserva el índice persistido en disco de la última vez online,
    # así la búsqueda con typos funciona igual en modo offline.
    try:
        from pos_uniformes.services.meilisearch_service import autostart_and_reindex
        autostart_and_reindex()
    except Exception as exc:  # noqa: BLE001
        print(f"Meilisearch no disponible: {exc}", file=sys.stderr)

    _show_splash_message(
        splash, "Buscando la PC principal…", "Es la que guarda las ventas y el catálogo.", 0.05
    )
    # Se espera un poco a que la PC principal aparezca. El caso que duele es la
    # luz: vuelve, todo se prende junto, el servidor tarda en levantar Postgres
    # y el kiosko —que bootea en segundos— probaba UNA vez y se quedaba en modo
    # local toda la mañana. Si ya está encendida, esto no cuesta nada: vuelve
    # en el primer intento.
    from pos_uniformes.services.satellite_startup_service import ESPERA_ARRANQUE_SEG, esperar_base

    def _esperando(intento: int, restan: int) -> None:
        # No solo cuánto falta: qué va a pasar cuando se acabe la espera.
        _show_splash_message(
            splash,
            "Esperando a la PC principal…",
            f"Todavía no contesta. Si en {int(restan)} s no aparece, abro con el catálogo guardado.",
            1 - (restan / ESPERA_ARRANQUE_SEG if ESPERA_ARRANQUE_SEG else 1),
        )

    connection_available = esperar_base(avisar=_esperando)

    window = None
    if connection_available:
        # El sondeo solo dice que el puerto contesta. Con la red parpadeando,
        # la conexión de verdad puede fallar un segundo después — y el 02/10 eso
        # dejó al kiosko SIN ABRIR («Arranque no disponible: connection timeout
        # expired») teniendo su modo local perfectamente bueno. Si cualquier
        # paso de aquí falla, se cae a local en vez de rendirse: un kiosko que
        # no abre es un kiosko que no vende.
        _show_splash_message(splash, "Conectando con la tienda…", "La PC principal ya contestó.", 0.45)
        try:
            bootstrap_schema()
            assert_database_ready()
            _show_splash_message(splash, "Cargando el catálogo…", "Escuelas, prendas y precios al día.", 0.75)
            operator_id = resolve_satellite_operator_id()
            window = QuoteSatelliteWindow(user_id=operator_id, offline_mode=False)
        except DatabasePreflightError as exc:
            # Esta sí para todo: la base está, pero con un esquema que este
            # programa no entiende. Abrir en local escondería el problema y
            # alguien vendería contra un catálogo que ya no cuadra.
            splash.close()
            QMessageBox.critical(None, "Base de datos no lista", str(exc))
            return 1
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "La base contestó el sondeo pero no la conexión (%s); se abre en local.", exc
            )
            connection_available = False

    if window is None:
        _show_splash_message(
            splash, "Abriendo en modo local",
            "La PC principal no contestó: trabajo con el catálogo guardado y subo las ventas cuando vuelva.", 0.75,
        )
        local_cache = load_catalog_cache()
        if local_cache is None:
            # Es el único caso en que de verdad no se puede abrir: sin catálogo
            # no hay precios ni SKUs que buscar. Se dice qué pasa y qué hacer,
            # sin pedirle que "revise la red" — eso no lo va a hacer nadie en
            # el mostrador.
            splash.close()
            QMessageBox.warning(
                None,
                "Falta encender la PC principal",
                "Esta pantalla todavía no tiene su copia del catálogo, y la PC "
                "principal (la de atrás) no contesta.\n\n"
                "Enciéndela, espera dos minutos y vuelve a abrir este programa.\n\n"
                "Si ya está encendida, avisa: puede ser la red.",
            )
            return 1
        window = QuoteSatelliteWindow(
            user_id=None,
            offline_mode=True,
            offline_catalog_cache=local_cache,
        )

    _show_splash_message(splash, "Listo", "", 1.0)
    window.showFullScreen()
    splash.finish(window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
