"""Consultas que se abren con una tecla, en el kiosko y en el POS (2026-11-07).

Daniel: «que el mapa de escuelas se abra también con una combinación de
teclas, igual otro para tipos de escocés».

- Ctrl+Shift+M — Mapa de escuelas (con el estado de los conteos de ahora).
- Ctrl+Shift+E — Tipos de escocés (ESC-01…ESC-37, el PDF de las dos hojas).

Las dos se abren en una ventana del programa (Daniel: «que se sienta algo
más del programa, como si fuera una ventana más»), ver
`ui/dialogs/visor_consulta_dialog.py`. Si la PC no tiene el motor web (el
ejecutable del kiosko no trae QtWebEngine: pesa ~150 MB), el mapa abre en
Edge en modo aplicación —una ventana sin pestañas ni barra de direcciones— y
si tampoco, en el navegador."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

logger = logging.getLogger(__name__)

ATAJO_MAPA = "Ctrl+Shift+M"
ATAJO_ESCOCES = "Ctrl+Shift+E"


def ruta_tipos_escoces() -> Path:
    # Va en assets/, que el ejecutable del satélite ya trae completo.
    return Path(__file__).resolve().parents[2] / "assets" / "catalogos" / "Tipos_de_Escoces.pdf"


def _abrir(ruta: Path) -> bool:
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(ruta)))


def ruta_edge() -> Path | None:
    if not sys.platform.startswith("win"):
        return None
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            ruta = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if ruta.is_file():
                return ruta
    return None


def _abrir_como_ventana(ruta: Path | str) -> bool:
    """Edge en modo aplicación: una ventana sola, sin pestañas ni dirección.

    `ruta` es un archivo local o una dirección de internet."""
    edge = ruta_edge()
    if edge is None:
        return False
    url = ruta if isinstance(ruta, str) else QUrl.fromLocalFile(str(ruta)).toString()
    try:
        subprocess.Popen([str(edge), f"--app={url}", "--window-size=1400,900"])
        return True
    except OSError:
        logger.warning("No se pudo abrir Edge en modo ventana", exc_info=True)
        return False


def _hay_motor_web() -> bool:
    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
    except ImportError:
        return False
    return True


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
    if _hay_motor_web():
        try:
            from pos_uniformes.ui.dialogs.visor_consulta_dialog import mostrar_mapa

            mostrar_mapa(html, parent)
            return
        except Exception:  # noqa: BLE001 — sin ventana propia, abre afuera
            logger.warning("Mapa de escuelas: no se pudo abrir la ventana", exc_info=True)
    if not _abrir_como_ventana(html):
        _abrir(html)


def abrir_tipos_escoces(parent: QWidget | None = None) -> None:
    # El catálogo de verdad (cuadrícula, buscar, ficha); el PDF solo si esta
    # PC todavía no tiene las fotos (2026-11-07).
    try:
        from pos_uniformes.ui.dialogs.visor_escoces_dialog import hay_catalogo, mostrar_escoces

        if hay_catalogo():
            mostrar_escoces(parent)
            return
    except Exception:  # noqa: BLE001 — sin el catálogo nuevo, el PDF de antes
        logger.warning("Tipos de escocés: no se pudo abrir el catálogo", exc_info=True)
    ruta = ruta_tipos_escoces()
    if not ruta.is_file():
        QMessageBox.information(parent, "Tipos de escocés", "Esta PC no tiene el catálogo de escoceses. Llega con la siguiente actualización.")
        return
    try:
        from pos_uniformes.ui.dialogs.visor_consulta_dialog import mostrar_pdf

        mostrar_pdf(ruta, "🧵 Tipos de escocés", parent)
    except Exception:  # noqa: BLE001 — sin QtPdf, el visor de la PC
        logger.warning("Tipos de escocés: no se pudo abrir la ventana", exc_info=True)
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


ATAJOS_BUSQUEDA_CONSULTA = ("Ctrl+S", "Meta+S")


def abrir_busqueda_de_consulta(parent: QWidget | None = None) -> None:
    """Buscar producto por texto y ver precio y existencia (2026-11-12).

    Antes Ctrl+S agregaba al carrito de la Caja antigua; con ella retirada
    (Daniel: «la caja antigua ya no es de utilidad, todo lo demás corre en
    libreta y kioskos») la búsqueda se queda en el POS solo para consultar."""
    from pos_uniformes.ui.dialogs.quick_product_search_dialog import QuickProductSearchDialog

    QuickProductSearchDialog(parent, solo_consulta=True).exec()


def instalar_busqueda_de_consulta(ventana: QWidget) -> list[QShortcut]:
    """Ctrl+S / Cmd+S del POS principal. El kiosko tiene su propio Ctrl+S."""
    atajos = []
    for tecla in ATAJOS_BUSQUEDA_CONSULTA:
        atajo = QShortcut(QKeySequence(tecla), ventana)
        atajo.activated.connect(lambda: abrir_busqueda_de_consulta(ventana))
        atajos.append(atajo)
    return atajos


def abrir_whatsapp_web(url: str, parent: QWidget | None = None) -> bool:
    """WhatsApp Web, nunca la app de escritorio (Daniel, 2026-11-10).

    Igual que el mapa: en una ventana del programa si hay motor web; si no
    (el kiosko), en Edge en modo aplicación; y si tampoco, en el navegador."""
    if _hay_motor_web():
        try:
            from pos_uniformes.ui.dialogs.visor_consulta_dialog import mostrar_whatsapp

            mostrar_whatsapp(url, parent)
            return True
        except Exception:  # noqa: BLE001 — sin ventana propia, abre afuera
            logger.warning("WhatsApp Web: no se pudo abrir la ventana", exc_info=True)
    if _abrir_como_ventana(url):
        return True
    return bool(QDesktopServices.openUrl(QUrl(url)))
