"""🗺 Mapa de conteos en el kiosko: qué está contado y qué no, por capas.

La misma página que el celular, pero armada aquí (HTML autónomo de
`conteo_mapa_service.html`) y mostrada en un QWebEngineView: no necesita
servidor de la PWA ni sesión. Se genera en un hilo (por Wi-Fi tarda unos
segundos) y la ve cualquiera que esté en Conteos, con o sin gafete.
"""

from __future__ import annotations

import logging
import threading

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

_CARGANDO = (
    "<html><body style='display:flex;justify-content:center;align-items:center;height:100vh;"
    "font-family:sans-serif;color:#888;background:#f4ede2'><div><h2>Armando el mapa de conteos…</h2>"
    "<p>Unos segundos: se revisa cada talla de cada escuela.</p></div></body></html>"
)


def generar_html() -> str:
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.conteo_mapa_service import html

    with get_session() as session:
        return html(session)


class ConteoMapaDialog(QDialog):
    _listo = pyqtSignal(str)   # html generado, o "" si falló

    def __init__(self, parent: QWidget | None = None, *, generar=generar_html) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mapa de conteos")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(1100, 760)
        self._generar = generar
        self._web = None
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)
        barra = QHBoxLayout()
        barra.setContentsMargins(12, 8, 12, 8)
        self.estado = QLabel("Armando el mapa…")
        self.estado.setStyleSheet("color: #8a7358; font-size: 13px;")
        barra.addWidget(self.estado, 1)
        self.refrescar_btn = QPushButton("↻ Actualizar")
        self.refrescar_btn.setAutoDefault(False)
        self.refrescar_btn.clicked.connect(self.recargar)
        barra.addWidget(self.refrescar_btn)
        cerrar = QPushButton("Cerrar")
        cerrar.setAutoDefault(False)
        cerrar.clicked.connect(self.accept)
        barra.addWidget(cerrar)
        ly.addLayout(barra)
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView

            self._web = QWebEngineView()
            ly.addWidget(self._web, 1)
        except Exception as exc:  # noqa: BLE001 — sin WebEngine se avisa y ya
            aviso = QLabel(f"No se puede mostrar el mapa aquí (falta PyQt6-WebEngine):\n{exc}")
            aviso.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ly.addWidget(aviso, 1)
        self._listo.connect(self._pintar)
        self.recargar()

    def recargar(self) -> None:
        self.refrescar_btn.setEnabled(False)
        self.estado.setText("Armando el mapa…")
        if self._web is not None:
            self._web.setHtml(_CARGANDO)

        def _worker() -> None:
            try:
                html = self._generar()
            except Exception:  # noqa: BLE001
                logger.exception("Mapa de conteos: no se pudo generar")
                html = ""
            try:
                self._listo.emit(html)
            except RuntimeError:
                pass

        threading.Thread(target=_worker, daemon=True, name="conteo-mapa").start()

    def _pintar(self, html: str) -> None:
        self.refrescar_btn.setEnabled(True)
        if not html:
            self.estado.setText("No se pudo armar el mapa (¿sin conexión con la PC principal?).")
            return
        self.estado.setText("Verde = al día · ámbar = ya venció · gris = nunca contada. Toca una escuela.")
        if self._web is not None:
            self._web.setHtml(html)
