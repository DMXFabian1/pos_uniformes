"""🗺 Mapa de conteos en el kiosko: qué está contado y qué no, por capas.

Pintado con texto enriquecido de Qt (`conteo_mapa_rich_text`), sin WebEngine
—el kiosko no lo trae y son ~200 MB por máquina—. Los datos se arman en un
hilo (por Wi-Fi tarda segundos). Vive dentro de la sección Conteos
(`ConteoMapaWidget`) y también como diálogo grande (`ConteoMapaDialog`).
"""

from __future__ import annotations

import logging
import threading
import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

from pos_uniformes.ui.helpers import conteo_mapa_rich_text as rt

logger = logging.getLogger(__name__)


def generar_datos() -> dict:
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.conteo_mapa_service import todo

    with get_session() as session:
        return todo(session)


class ConteoMapaWidget(QWidget):
    """Barra (buscador, estado, ↻) + una QLabel enriquecida con la capa actual."""

    _listo = pyqtSignal(object)   # dict de datos, o None si falló

    def __init__(self, parent: QWidget | None = None, *, generar=generar_datos, auto: bool = True, columnas: int = 4, scroll_propio: bool = True) -> None:
        """`scroll_propio=False`: dentro de una página que ya hace scroll (la
        sección Conteos) el mapa crece a su tamaño, sin scroll anidado."""
        super().__init__(parent)
        self._generar = generar
        self._columnas = columnas
        self._datos: dict | None = None
        self._capa: str = "mapa"          # "mapa" o la clave de detalle ("e19" / "bPantalón")
        self._abiertas: set[int] = set()  # prendas desplegadas en el detalle
        self._generando = False
        self._generado_en: float = 0.0
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(6)
        barra = QHBoxLayout()
        barra.setContentsMargins(0, 0, 0, 0)
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar escuela…")
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(lambda _t: self._pintar())
        barra.addWidget(self.busca, 1)
        self.estado = QLabel("")
        self.estado.setStyleSheet("color: #8a7358; font-size: 12px;")
        barra.addWidget(self.estado, 2)
        self.refrescar_btn = QPushButton("↻ Actualizar")
        self.refrescar_btn.setAutoDefault(False)
        self.refrescar_btn.clicked.connect(lambda: self.recargar(forzar=True))
        barra.addWidget(self.refrescar_btn)
        ly.addLayout(barra)
        self.cuerpo = QLabel("Armando el mapa…")
        self.cuerpo.setWordWrap(True)
        self.cuerpo.setTextFormat(Qt.TextFormat.RichText)
        self.cuerpo.setOpenExternalLinks(False)
        self.cuerpo.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.cuerpo.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.cuerpo.linkActivated.connect(self._navegar)
        # Colores explícitos: con el modo oscuro del sistema, el área con scroll
        # heredaba un fondo negro y el texto (del mismo color) desaparecía.
        self.cuerpo.setStyleSheet("background: #f4ede2; color: #2c2a27; font-size: 13px; padding: 2px;")
        self.cuerpo.setAutoFillBackground(True)
        if scroll_propio:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
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
        self.estado.setText("Verde = al día · ámbar = ya venció · gris = nunca · naranja = en proceso. Toca una escuela; luego una prenda.")
        self._pintar()

    # ── capas ──
    def _navegar(self, href: str) -> None:
        if href == "mapa":
            self._capa, self._abiertas = "mapa", set()
        elif href.startswith("p") and href[1:].isdigit():
            i = int(href[1:])
            self._abiertas ^= {i}
        else:
            self._capa, self._abiertas = href, set()
        self._pintar()
        if self.scroll is not None:
            self.scroll.verticalScrollBar().setValue(0)

    def _pintar(self) -> None:
        if not self._datos:
            return
        if self._capa == "mapa":
            self.cuerpo.setText(rt.mapa(self._datos, columnas=self._columnas, filtro=self.busca.text()))
            self.busca.setVisible(True)
        else:
            d = self._datos.get("detalles", {}).get(self._capa)
            if d is None:
                self._capa = "mapa"
                return self._pintar()
            self.cuerpo.setText(rt.detalle(d, abiertas=self._abiertas))
            self.busca.setVisible(False)


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
