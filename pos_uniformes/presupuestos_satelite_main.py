"""Punto de entrada para la app satelite de Presupuestos."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pos_uniformes.database.connection import init_db
from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import RolUsuario
from pos_uniformes.database.models import Usuario
from pos_uniformes.database.preflight import DatabasePreflightError, assert_database_ready
from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow
from pos_uniformes.utils.config import settings


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


def main() -> int:
    bootstrap_schema()

    app = QApplication(sys.argv)
    try:
        assert_database_ready()
    except DatabasePreflightError as exc:
        QMessageBox.critical(None, "Base de datos no lista", str(exc))
        return 1

    try:
        operator_id = resolve_satellite_operator_id()
        window = QuoteSatelliteWindow(user_id=operator_id)
    except Exception as exc:
        QMessageBox.critical(None, "Arranque no disponible", str(exc))
        return 1
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
