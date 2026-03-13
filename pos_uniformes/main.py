"""Punto de entrada de la aplicacion POS Uniformes."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox
from sqlalchemy.exc import SQLAlchemyError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pos_uniformes.database.connection import init_db
from pos_uniformes.database.preflight import DatabasePreflightError, assert_database_ready
from pos_uniformes.ui.login_dialog import LoginDialog
from pos_uniformes.ui.main_window import MainWindow
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
    if login_dialog.exec() != LoginDialog.DialogCode.Accepted or login_dialog.user_id is None:
        return 0

    window = MainWindow(user_id=login_dialog.user_id)
    if not window.ensure_cash_session():
        return 0
    window.refresh_all()
    window._focus_default_tab_for_role()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
