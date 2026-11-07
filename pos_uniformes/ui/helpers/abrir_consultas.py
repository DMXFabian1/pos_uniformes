"""Consultas que se abren con una tecla, en el kiosko y en el POS (2026-11-07).

Daniel: «que el mapa de escuelas se abra también con una combinación de
teclas, igual otro para tipos de escocés».

- Ctrl+Shift+M — Mapa de escuelas (con el estado de los conteos de ahora).
- Ctrl+Shift+E — Tipos de escocés (ESC-01…ESC-37, el PDF de las dos hojas).

Las dos se abren en el programa de la PC (navegador / visor de PDF)."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

ATAJO_MAPA = "Ctrl+Shift+M"
ATAJO_ESCOCES = "Ctrl+Shift+E"


def ruta_tipos_escoces() -> Path:
    # Va en assets/, que el ejecutable del satélite ya trae completo.
    return Path(__file__).resolve().parents[2] / "assets" / "catalogos" / "Tipos_de_Escoces.pdf"


def _abrir(ruta: Path) -> bool:
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(ruta)))


def abrir_mapa_escuelas(parent: QWidget | None = None) -> None:
    from pos_uniformes.services import mapa_escuelas_service

    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        html = mapa_escuelas_service.preparar()
    finally:
        QApplication.restoreOverrideCursor()
    if html is None:
        QMessageBox.information(parent, "Mapa de escuelas", "Esta PC no tiene el mapa de escuelas. Llega con la siguiente actualización.")
        return
    _abrir(html)


def abrir_tipos_escoces(parent: QWidget | None = None) -> None:
    ruta = ruta_tipos_escoces()
    if not ruta.is_file():
        QMessageBox.information(parent, "Tipos de escocés", "Esta PC no tiene el catálogo de escoceses. Llega con la siguiente actualización.")
        return
    _abrir(ruta)


def instalar_atajos(ventana: QWidget) -> list[QShortcut]:
    """Los dos atajos sobre `ventana` (funcionan en cualquier pantalla de ella)."""
    atajos = []
    for tecla, accion in ((ATAJO_MAPA, abrir_mapa_escuelas), (ATAJO_ESCOCES, abrir_tipos_escoces)):
        atajo = QShortcut(QKeySequence(tecla), ventana)
        atajo.setContext(Qt.ShortcutContext.WindowShortcut)
        atajo.activated.connect(lambda accion=accion: accion(ventana))
        atajos.append(atajo)
    return atajos
