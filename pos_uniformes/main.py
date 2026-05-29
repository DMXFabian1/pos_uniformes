"""Punto de entrada de la aplicacion POS Uniformes."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pos_uniformes.utils.venv_bootstrap import ensure_local_venv_site_packages

ensure_local_venv_site_packages(Path(__file__))

# QtWebEngineWidgets debe importarse ANTES de crear QApplication
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    print("[main] QtWebEngineWidgets cargado OK")
except Exception as _webengine_exc:
    print(f"[main] QtWebEngineWidgets no disponible: {_webengine_exc}")

# ---------------------------------------------------------------------------
# Auto-detección de DB — debe correr ANTES de importar connection.py
# Windows (LAN) → usa DB de producción directo
# Sin LAN        → usa DB local de Mac
# ---------------------------------------------------------------------------
import os as _os
import socket as _socket


def _detect_db_mode() -> str:
    _win = "192.168.0.10"
    if _os.getenv("POS_UNIFORMES_DB_HOST"):
        return "configured"
    try:
        _s = _socket.create_connection((_win, 5432), timeout=1)
        _s.close()
        _os.environ["POS_UNIFORMES_DB_HOST"] = _win
        return "windows"
    except OSError:
        return "local"


_DB_MODE = _detect_db_mode()
# ---------------------------------------------------------------------------

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox
from sqlalchemy.exc import SQLAlchemyError

from pos_uniformes.database.connection import init_db
from pos_uniformes.database.preflight import DatabasePreflightError, assert_database_ready
from pos_uniformes.ui.login_dialog import LoginDialog
from pos_uniformes.ui.main_window import MainWindow
from pos_uniformes.utils.app_metadata import (
    APP_DISPLAY_NAME,
    APP_ORGANIZATION_NAME,
    app_icon_path,
    app_version,
)
from pos_uniformes.utils.config import settings


def bootstrap_schema() -> None:
    """Crea las tablas solo cuando se habilita explicitamente."""
    if not settings.auto_create_schema:
        return

    try:
        init_db()
    except SQLAlchemyError as exc:
        print(f"No fue posible inicializar el esquema: {exc}", file=sys.stderr)


def main() -> int:
    bootstrap_schema()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setOrganizationName(APP_ORGANIZATION_NAME)
    app.setApplicationVersion(app_version())
    icon_path = app_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))
    try:
        assert_database_ready()
    except DatabasePreflightError as exc:
        QMessageBox.critical(
            None,
            "Base de datos no lista",
            str(exc),
        )
        return 1

    # Sincronizar DB remota → local (solo cuando NO usamos Windows directamente)
    try:
        import platform
        if platform.system() == "Darwin" and _DB_MODE == "local":
            from pos_uniformes.services.db_sync_service import can_sync, sync_remote_to_local
            ok, _reason = can_sync()
            if ok:
                success, msg = sync_remote_to_local()
                if success:
                    print(f"DB sync: {msg}", file=sys.stderr)
                else:
                    print(f"DB sync omitido: {msg}", file=sys.stderr)
    except Exception:
        pass

    try:
        from pos_uniformes.services.meilisearch_service import notify_catalog_changed
        notify_catalog_changed()
    except Exception:
        pass

    login_dialog = LoginDialog()
    _mode_suffix = "  🟢 Tienda" if _DB_MODE == "windows" else "  🟡 Local"
    login_dialog.setWindowTitle(f"Acceso{_mode_suffix}")
    startup_window: MainWindow | None = None

    def _launch_main_window(user_id: int) -> None:
        nonlocal startup_window
        try:
            login_dialog.hide()
            startup_window = MainWindow(user_id=user_id)
            if not startup_window.ensure_cash_session():
                login_dialog.clear_loading_state()
                login_dialog.show()
                login_dialog.raise_()
                login_dialog.activateWindow()
                return
            startup_window.refresh_all()
            startup_window._focus_default_tab_for_role()
        except Exception as exc:  # noqa: BLE001
            if startup_window is not None:
                startup_window.close()
                startup_window = None
            login_dialog.clear_loading_state()
            login_dialog.show()
            QMessageBox.critical(login_dialog, "No se pudo iniciar la aplicacion", str(exc))
            login_dialog.raise_()
            login_dialog.activateWindow()
            return

        login_dialog.clear_loading_state()
        login_dialog.accept()
        startup_window.showMaximized()
        startup_window.setWindowTitle(startup_window.windowTitle() + _mode_suffix)

    login_dialog.authenticated.connect(_launch_main_window)
    login_dialog.rejected.connect(app.quit)
    login_dialog.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
