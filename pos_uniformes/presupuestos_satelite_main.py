"""Punto de entrada para la app satelite de Presupuestos."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pos_uniformes.utils.venv_bootstrap import ensure_local_venv_site_packages

ensure_local_venv_site_packages(Path(__file__))

from PyQt6.QtCore import QLockFile, QStandardPaths, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen
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


def _build_splash_pixmap() -> QPixmap:
    W, H = 520, 300
    pix = QPixmap(W, H)
    pix.fill(QColor("#f4ede0"))

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Barra superior de acento
    painter.fillRect(0, 0, W, 8, QColor("#a84f2d"))

    # Nombre de la app
    font_title = QFont()
    font_title.setPointSize(28)
    font_title.setWeight(QFont.Weight.Black)
    painter.setFont(font_title)
    painter.setPen(QColor("#2f2a24"))
    painter.drawText(0, 60, W, 50, Qt.AlignmentFlag.AlignHCenter, "Presupuestos Satélite")

    # Subtítulo
    font_sub = QFont()
    font_sub.setPointSize(13)
    font_sub.setWeight(QFont.Weight.Normal)
    painter.setFont(font_sub)
    painter.setPen(QColor("#87492c"))
    painter.drawText(0, 118, W, 30, Qt.AlignmentFlag.AlignHCenter, "Maximoda")

    # Separador
    painter.setPen(QColor("#ddd0be"))
    painter.drawLine(60, 168, W - 60, 168)

    # Mensaje de carga (placeholder — se actualiza via showMessage)
    painter.end()
    return pix


def _show_splash_message(splash: QSplashScreen, msg: str, app: QApplication) -> None:
    splash.showMessage(
        msg,
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#87492c"),
    )
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


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(satellite_display_name())
    app.setOrganizationName("POSUniformes")
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

    # ── Splash ────────────────────────────────────────────────────────
    splash = QSplashScreen(_build_splash_pixmap())
    splash.setFont(QFont("", 11))
    splash.show()
    app.processEvents()

    # ── Arranque ──────────────────────────────────────────────────────
    _show_splash_message(splash, "Verificando conexión...", app)
    connection_available = probe_database_host()

    if connection_available:
        _show_splash_message(splash, "Preparando base de datos...", app)
        bootstrap_schema()
        try:
            assert_database_ready()
        except DatabasePreflightError as exc:
            splash.close()
            QMessageBox.critical(None, "Base de datos no lista", str(exc))
            return 1

        _show_splash_message(splash, "Cargando catálogo...", app)
        try:
            operator_id = resolve_satellite_operator_id()
            window = QuoteSatelliteWindow(user_id=operator_id, offline_mode=False)
        except Exception as exc:
            splash.close()
            QMessageBox.critical(None, "Arranque no disponible", str(exc))
            return 1
    else:
        _show_splash_message(splash, "Sin conexión — cargando catálogo local...", app)
        local_cache = load_catalog_cache()
        if local_cache is None:
            splash.close()
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

    _show_splash_message(splash, "Listo.", app)
    window.showFullScreen()
    splash.finish(window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
