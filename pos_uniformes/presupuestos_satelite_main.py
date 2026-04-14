"""Punto de entrada para la app satelite de Presupuestos."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pos_uniformes.utils.venv_bootstrap import ensure_local_venv_site_packages

ensure_local_venv_site_packages(Path(__file__))

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
    app = QApplication(sys.argv)
    app.setApplicationName(satellite_display_name())
    app.setOrganizationName("POSUniformes")
    icon_path = satellite_windows_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    # Prueba rapida de conexion (TCP, 3s). No lanza excepciones.
    connection_available = probe_database_host()

    if connection_available:
        # Flujo normal: conexion con la PC principal disponible.
        bootstrap_schema()
        try:
            assert_database_ready()
        except DatabasePreflightError as exc:
            QMessageBox.critical(None, "Base de datos no lista", str(exc))
            return 1
        try:
            operator_id = resolve_satellite_operator_id()
            window = QuoteSatelliteWindow(user_id=operator_id, offline_mode=False)
        except Exception as exc:
            QMessageBox.critical(None, "Arranque no disponible", str(exc))
            return 1
    else:
        # Sin conexion: intentar abrir con la ultima cache local del catalogo.
        local_cache = load_catalog_cache()
        if local_cache is None:
            QMessageBox.warning(
                None,
                "Sin conexion y sin catalogo guardado",
                "No se pudo conectar con la PC principal y no hay un catalogo guardado localmente.\n\n"
                "Enciende la PC principal, conéctate a la red y vuelve a abrir el programa.",
            )
            return 1
        window = QuoteSatelliteWindow(
            user_id=None,
            offline_mode=True,
            offline_catalog_cache=local_cache,
        )

    window.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
