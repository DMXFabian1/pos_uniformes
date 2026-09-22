"""🗺 Mapa de conteos en el kiosko: qué está contado y qué no, por capas.

Con los mismos widgets del kiosko (tarjetas `libretaCard`, títulos
`libretaSeccion`; ver `ui/helpers/conteo_mapa_widgets.py`), sin WebEngine —el
kiosko no lo trae y son ~200 MB por máquina—. Los datos se arman en un hilo
(por Wi-Fi tarda segundos). Vive dentro de la sección Conteos
(`ConteoMapaWidget`) y también como diálogo grande (`ConteoMapaDialog`).
"""

from __future__ import annotations

import logging
import threading
import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

from pos_uniformes.ui.helpers.conteo_mapa_widgets import CapaDetalle, CapaMapa

logger = logging.getLogger(__name__)


def generar_datos() -> dict:
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.conteo_mapa_service import todo

    with get_session() as session:
        return todo(session)


class ConteoMapaWidget(QWidget):
    """Barra (buscador, estado, ↻) + la capa actual (mapa o detalle)."""

    _listo = pyqtSignal(object)   # dict de datos, o None si falló
    #: (escuela_id | None, tipo_pieza, prenda) — el botón de una prenda del mapa.
    imprimir_prenda = pyqtSignal(object, str, str)

    def __init__(self, parent: QWidget | None = None, *, generar=generar_datos, auto: bool = True, columnas: int = 4, scroll_propio: bool = True) -> None:
        """`scroll_propio=False`: dentro de una página que ya hace scroll (la
        sección Conteos) el mapa crece a su tamaño, sin scroll anidado."""
        super().__init__(parent)
        self._generar = generar
        self._columnas = columnas
        self._datos: dict | None = None
        self._capa: str = "mapa"          # "mapa" o la clave de detalle ("e19" / "bPantalón")
        self._generando = False
        self._generado_en: float = 0.0
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(8)
        barra = QHBoxLayout()
        barra.setContentsMargins(0, 0, 0, 0)
        barra.setSpacing(10)
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar escuela…")
        self.busca.setClearButtonEnabled(True)
        self.busca.setMaximumWidth(320)
        self.busca.textChanged.connect(lambda _t: self._pintar())
        barra.addWidget(self.busca)
        self.estado = QLabel("")
        self.estado.setObjectName("libretaSubtitulo")
        self.estado.setWordWrap(True)
        barra.addWidget(self.estado, 1)
        self.refrescar_btn = QPushButton("↻ Actualizar")
        self.refrescar_btn.setObjectName("secondaryButton")
        self.refrescar_btn.setAutoDefault(False)
        self.refrescar_btn.clicked.connect(lambda: self.recargar(forzar=True))
        barra.addWidget(self.refrescar_btn)
        ly.addLayout(barra)
        # El cuerpo es un contenedor cuyo único hijo se reemplaza por capa.
        self.cuerpo = QWidget()
        self._cuerpo_ly = QVBoxLayout(self.cuerpo)
        self._cuerpo_ly.setContentsMargins(0, 0, 0, 0)
        self._capa_widget: QWidget | None = None
        aviso = QLabel("Armando el mapa…")
        aviso.setObjectName("libretaPanelVacio")
        self._poner(aviso)
        if scroll_propio:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)   # ancho fijo: las tarjetas no se cortan al aparecer
            scroll.setStyleSheet("QScrollArea { background: #f4ede2; border: none; } QScrollArea > QWidget > QWidget { background: #f4ede2; }")
            scroll.viewport().setStyleSheet("background: #f4ede2;")
            scroll.setWidget(self.cuerpo)
            self.scroll = scroll
            ly.addWidget(scroll, 1)
        else:
            self.scroll = None
            ly.addWidget(self.cuerpo, 1)
        self._listo.connect(self._recibir)
        if auto:
            self.recargar(forzar=True)

    def _poner(self, w: QWidget) -> None:
        if self._capa_widget is not None:
            viejo = self._capa_widget
            self._cuerpo_ly.removeWidget(viejo)
            viejo.hide()            # que no se vea "por detrás" mientras Qt lo borra
            viejo.setParent(None)
            viejo.deleteLater()
        self._capa_widget = w
        self._cuerpo_ly.addWidget(w)

    # ── datos ──
    def recargar(self, *, forzar: bool = False, cada_seg: float = 60.0) -> bool:
        """Vuelve a armar los datos en un hilo. Sin `forzar`, no más de una vez
        por minuto: la sección se refresca a cada rato. Devuelve si arrancó."""
        if self._generando:
            return False
        if not forzar and self._generado_en and time.monotonic() - self._generado_en < cada_seg:
            return False
        self._generando = True
        self.refrescar_btn.setEnabled(False)
        self.estado.setText("Armando el mapa…")

        def _worker() -> None:
            try:
                datos = self._generar()
            except Exception:  # noqa: BLE001
                logger.exception("Mapa de conteos: no se pudo generar")
                datos = None
            try:
                self._listo.emit(datos)
            except RuntimeError:
                pass

        threading.Thread(target=_worker, daemon=True, name="conteo-mapa").start()
        return True

    def _recibir(self, datos) -> None:
        self._generando = False
        self.refrescar_btn.setEnabled(True)
        if not datos:
            self.estado.setText("No se pudo armar el mapa (¿sin conexión con la PC principal?).")
            return
        self._datos = datos
        self._generado_en = time.monotonic()
        self.estado.setText("Toca una escuela o un tipo de básicos; luego una prenda para ver sus tallas.")
        self._pintar()

    # ── capas ──
    def _navegar(self, href: str) -> None:
        self._capa = "mapa" if href == "mapa" else href
        self._pintar()
        if self.scroll is not None:
            self.scroll.verticalScrollBar().setValue(0)

    def _pintar(self) -> None:
        if not self._datos:
            return
        if self._capa == "mapa":
            capa = CapaMapa(self._datos, columnas=self._columnas, filtro=self.busca.text())
            capa.elegido.connect(self._navegar)
            self.busca.setVisible(True)
        else:
            d = self._datos.get("detalles", {}).get(self._capa)
            if d is None:
                self._capa = "mapa"
                return self._pintar()
            capa = CapaDetalle(d)
            capa.volver.connect(lambda: self._navegar("mapa"))
            capa.imprimir_prenda.connect(self._pedir_hoja)
            self.busca.setVisible(False)
        self._poner(capa)

    def _pedir_hoja(self, prenda: str) -> None:
        """Traduce la capa que se está viendo al alcance que espera quien imprime.

        Las claves del mapa son `e<escuela_id>` y `b<tipo de básicos>`."""
        capa = str(self._capa or "")
        if capa.startswith("e") and capa[1:].isdigit():
            self.imprimir_prenda.emit(int(capa[1:]), "", prenda)
        elif capa.startswith("b"):
            self.imprimir_prenda.emit(None, capa[1:], prenda)


class ConteoMapaDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, generar=generar_datos) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mapa de conteos")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(1100, 760)
        self.setStyleSheet("QDialog { background: #f4ede2; } QLabel { color: #2c2a27; } QLineEdit { background: #fffdf8; color: #2c2a27; }")
        ly = QVBoxLayout(self)
        ly.setContentsMargins(12, 12, 12, 12)
        self.mapa = ConteoMapaWidget(self, generar=generar)
        ly.addWidget(self.mapa, 1)
        cerrar = QPushButton("Cerrar")
        cerrar.setAutoDefault(False)
        cerrar.clicked.connect(self.accept)
        ly.addWidget(cerrar)

    @property
    def estado(self) -> QLabel:
        return self.mapa.estado

    @property
    def refrescar_btn(self) -> QPushButton:
        return self.mapa.refrescar_btn
