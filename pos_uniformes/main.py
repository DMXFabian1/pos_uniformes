"""Punto de entrada de la aplicacion POS Uniformes."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pos_uniformes.utils.venv_bootstrap import ensure_local_venv_site_packages

ensure_local_venv_site_packages(Path(__file__))

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

    login_dialog = LoginDialog()
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

    login_dialog.authenticated.connect(_launch_main_window)
    login_dialog.rejected.connect(app.quit)
    login_dialog.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
