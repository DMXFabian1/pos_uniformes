"""Las consultas (mapa de escuelas, tipos de escocés) en una ventana del
programa, no en el navegador (2026-11-07).

Daniel: «al usar los comandos para ver mapa y ver pdf abre el navegador, me
gustaría que se sintiera algo más del programa, como si fuera una ventana más».

- `VisorMapa`: el mapa (Leaflet) en un QWebEngineView. Necesita internet
  para los mosaicos, igual que en el navegador. 🖨 imprime desde aquí.
- `VisorPdf`: el PDF en un QPdfView (QtPdf viene en PyQt6, también en el
  ejecutable del kiosko), ajustado al ancho, con zoom.

Una ventana por consulta: volver a pedirla la trae al frente (y el mapa se
recarga con el estado de ahora). Esc la cierra."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_VINO = "#6b1f3a"

_ESTILO = f"""
QWidget#barraVisor {{ background: {_VINO}; }}
QLabel#tituloVisor {{ color: white; font-size: 16px; font-weight: 600; }}
QLabel#detalleVisor {{ color: rgba(255,255,255,0.75); font-size: 13px; }}
QWidget#barraVisor QPushButton {{
    color: white; background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
    border-radius: 6px; padding: 6px 12px; font-size: 13px;
}}
QWidget#barraVisor QPushButton:hover {{ background: rgba(255,255,255,0.22); }}
QWidget#barraVisor QPushButton:disabled {{ color: rgba(255,255,255,0.35); }}
"""

#: Las ventanas abiertas, por consulta: pedirla otra vez la trae al frente.
_ABIERTAS: dict[str, "_Visor"] = {}


class _Visor(QDialog):
    """Ventana del programa con su barra (título · acciones · Cerrar)."""

    clave = ""

    def __init__(self, titulo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setObjectName("visorConsulta")
        self.setStyleSheet(_ESTILO)
        # Ventana normal (minimizar/maximizar), no un cuadro de diálogo.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self.barra = QWidget(objectName="barraVisor")
        fila = QHBoxLayout(self.barra)
        fila.setContentsMargins(16, 10, 12, 10)
        fila.setSpacing(8)
        self.titulo = QLabel(titulo, objectName="tituloVisor")
        self.detalle = QLabel("", objectName="detalleVisor")
        fila.addWidget(self.titulo)
        fila.addWidget(self.detalle)
        fila.addStretch(1)
        self.acciones = QHBoxLayout()
        self.acciones.setSpacing(8)
        fila.addLayout(self.acciones)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.close)
        fila.addWidget(cerrar)
        raiz.addWidget(self.barra)

        self.cuerpo = QVBoxLayout()
        self.cuerpo.setContentsMargins(0, 0, 0, 0)
        raiz.addLayout(self.cuerpo, 1)

        QShortcut(QKeySequence("Esc"), self, activated=self.close)
        self._dimensionar()

    def boton(self, texto: str, accion) -> QPushButton:
        b = QPushButton(texto)
        b.clicked.connect(accion)
        self.acciones.addWidget(b)
        return b

    def _dimensionar(self) -> None:
        pantalla = (self.parentWidget().screen() if self.parentWidget() else None) or QApplication.primaryScreen()
        if pantalla is None:
            self.resize(1200, 800)
            return
        area = pantalla.availableGeometry()
        self.resize(int(area.width() * 0.9), int(area.height() * 0.9))
        self.move(area.center() - self.rect().center())

    def traer_al_frente(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:  # noqa: N802
        if _ABIERTAS.get(self.clave) is self:
            _ABIERTAS.pop(self.clave, None)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Mapa
# ---------------------------------------------------------------------------


class VisorMapa(_Visor):
    clave = "mapa"

    def __init__(self, html: Path, parent: QWidget | None = None) -> None:
        from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
        from PyQt6.QtWebEngineWidgets import QWebEngineView

        super().__init__("🏫 Mapa de escuelas", parent)
        self.detalle.setText("San Felipe · los anillos son los conteos de ahora")
        self.html = Path(html)
        self._impresora = None

        class _Pagina(QWebEnginePage):
            # Un enlace a internet (Google Maps, la SEP) va al navegador; el
            # mapa no se reemplaza por otra página.
            def acceptNavigationRequest(self, url, tipo, principal):  # noqa: N802
                if tipo == QWebEnginePage.NavigationType.NavigationTypeLinkClicked and url.scheme() in ("http", "https"):
                    QDesktopServices.openUrl(url)
                    return False
                return super().acceptNavigationRequest(url, tipo, principal)

            def createWindow(self, _tipo):  # noqa: N802 — target=_blank: al navegador
                return None

        self.vista = QWebEngineView(self)
        self.vista.setPage(_Pagina(self.vista))
        ajustes = self.vista.settings()
        # El mapa es un archivo local que trae Leaflet y los mosaicos de internet
        # y su `estados_pos.js` de junto.
        ajustes.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        ajustes.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.vista.page().printRequested.connect(self.imprimir)
        self.cuerpo.addWidget(self.vista)

        self.boton("↻ Actualizar conteos", self.recargar)
        self.boton("🖨 Imprimir", self.imprimir)
        self.boton("Abrir en el navegador", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.html))))
        self.vista.load(QUrl.fromLocalFile(str(self.html)))

    def recargar(self) -> None:
        """Vuelve a calcular el estado de los conteos y recarga."""
        from pos_uniformes.services import mapa_escuelas_service

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            html = mapa_escuelas_service.preparar(self.html.parent)
        finally:
            QApplication.restoreOverrideCursor()
        if html is not None:
            self.html = html
        self.vista.reload()

    def imprimir(self) -> None:
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

        impresora = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialogo = QPrintDialog(impresora, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        # La impresión es asíncrona: la impresora tiene que vivir hasta que acabe.
        self._impresora = impresora
        self.vista.print(impresora)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


class VisorPdf(_Visor):
    clave = "pdf"

    def __init__(self, ruta: Path, titulo: str, parent: QWidget | None = None) -> None:
        from PyQt6.QtPdf import QPdfDocument
        from PyQt6.QtPdfWidgets import QPdfView

        super().__init__(titulo, parent)
        self.ruta = Path(ruta)
        self.documento = QPdfDocument(self)
        self.documento.load(str(self.ruta))
        paginas = self.documento.pageCount()
        self.detalle.setText(f"{paginas} hoja{'s' if paginas != 1 else ''}")

        self.vista = QPdfView(self)
        self.vista.setDocument(self.documento)
        self.vista.setPageMode(QPdfView.PageMode.MultiPage)
        self.vista.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.vista.setPageSpacing(16)
        self.vista.setStyleSheet("QPdfView { background: #ece7e2; }")
        self.cuerpo.addWidget(self.vista)

        self.boton("−", lambda: self._zoom(1 / 1.2)).setFixedWidth(40)
        self.boton("Ajustar al ancho", self._ajustar)
        self.boton("+", lambda: self._zoom(1.2)).setFixedWidth(40)
        # QtPdf no imprime: para eso, el visor de PDF de la PC.
        self.boton("🖨 Imprimir…", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ruta))))
        QShortcut(QKeySequence.StandardKey.ZoomIn, self, activated=lambda: self._zoom(1.2))
        QShortcut(QKeySequence.StandardKey.ZoomOut, self, activated=lambda: self._zoom(1 / 1.2))
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self._ajustar)

    def _zoom(self, factor: float) -> None:
        from PyQt6.QtPdfWidgets import QPdfView

        actual = self.vista.zoomFactor()
        self.vista.setZoomMode(QPdfView.ZoomMode.Custom)
        self.vista.setZoomFactor(max(0.25, min(5.0, actual * factor)))

    def _ajustar(self) -> None:
        from PyQt6.QtPdfWidgets import QPdfView

        self.vista.setZoomMode(QPdfView.ZoomMode.FitToWidth)


# ---------------------------------------------------------------------------


def mostrar_mapa(html: Path, parent: QWidget | None = None) -> VisorMapa:
    """Abre el mapa (o trae al frente el que ya está, con los conteos de ahora)."""
    ya = _ABIERTAS.get(VisorMapa.clave)
    if ya is not None:
        ya.html = Path(html)
        ya.vista.load(QUrl.fromLocalFile(str(html)))
        ya.traer_al_frente()
        return ya
    visor = VisorMapa(html, parent)
    _ABIERTAS[VisorMapa.clave] = visor
    visor.show()
    return visor


def mostrar_pdf(ruta: Path, titulo: str, parent: QWidget | None = None) -> VisorPdf:
    ya = _ABIERTAS.get(VisorPdf.clave)
    if ya is not None and ya.ruta == Path(ruta):
        ya.traer_al_frente()
        return ya
    if ya is not None:
        ya.close()
    visor = VisorPdf(ruta, titulo, parent)
    _ABIERTAS[VisorPdf.clave] = visor
    visor.show()
    return visor
