"""Overlay a pantalla completa que muestra un anuncio (cartelera o aviso).

Widget "tonto": sabe pintar UN anuncio (imagen o texto grande) cubriendo toda la
ventana y avisar cuando el usuario lo descarta (toca/teclea). La rotación de la
cartelera, la inactividad y qué anuncio toca los maneja `AnuncioCartelera`.

Reutilizable para los dos modos que pidió el usuario:
- Cartelera: se muestra al estar inactivo y rota entre los anuncios activos.
- Aviso inmediato: se muestra apenas llega un NOTIFY de un anuncio nuevo.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

# Paleta cálida MAXIMODA (misma que el resto del satélite).
_BG = "#7b2d14"       # marrón/rojo de marca — fondo de anuncios de texto
_BG_IMG = "#1a1a1a"   # casi negro — fondo para imágenes (letterbox)
_TITULO = "#fdfaf6"   # crema
_MENSAJE = "#f3e9dd"
_HINT = "#e8c9a0"


class AnuncioOverlay(QWidget):
    """Cubre la ventana y pinta un anuncio. Emite `descartado` al interactuar."""

    descartado = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("anuncioOverlay")
        self.setAutoFillBackground(True)
        # Recibe foco para capturar teclado; el mouse se maneja en mousePressEvent.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._pixmap_original: QPixmap | None = None
        self._modo_imagen = False

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setScaledContents(False)

        self._title_label = QLabel(self)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet(
            f"color: {_TITULO}; font-size: 64px; font-weight: 800;"
        )

        self._message_label = QLabel(self)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setWordWrap(True)
        self._message_label.setStyleSheet(f"color: {_MENSAJE}; font-size: 40px;")

        self._hint_label = QLabel("Toca la pantalla para volver", self)
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setStyleSheet(f"color: {_HINT}; font-size: 20px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 32)
        layout.addStretch(1)
        layout.addWidget(self._image_label)
        layout.addWidget(self._title_label)
        layout.addWidget(self._message_label)
        layout.addStretch(1)
        layout.addWidget(self._hint_label)

    # ── API ──────────────────────────────────────────────────────────────────

    def render_anuncio(self, anuncio: dict) -> None:
        """Pinta el anuncio dado. Usa `imagen_path` si existe; si no, texto."""
        imagen_path = anuncio.get("imagen_path")
        pixmap = QPixmap(imagen_path) if imagen_path else QPixmap()
        if imagen_path and not pixmap.isNull():
            self._render_imagen(pixmap)
        else:
            self._render_texto(anuncio.get("titulo"), anuncio.get("mensaje"))

    def _render_imagen(self, pixmap: QPixmap) -> None:
        self._modo_imagen = True
        self._pixmap_original = pixmap
        self._title_label.setVisible(False)
        self._message_label.setVisible(False)
        self._image_label.setVisible(True)
        self.setStyleSheet(f"#anuncioOverlay {{ background-color: {_BG_IMG}; }}")
        self._reescalar_pixmap()

    def _render_texto(self, titulo: str | None, mensaje: str | None) -> None:
        self._modo_imagen = False
        self._pixmap_original = None
        self._image_label.setVisible(False)
        self.setStyleSheet(f"#anuncioOverlay {{ background-color: {_BG}; }}")
        self._title_label.setText(titulo or "")
        self._title_label.setVisible(bool(titulo))
        self._message_label.setText(mensaje or "")
        self._message_label.setVisible(bool(mensaje))

    def _reescalar_pixmap(self) -> None:
        if not self._modo_imagen or self._pixmap_original is None:
            return
        area = self._image_label.size()
        if area.width() <= 0 or area.height() <= 0:
            return
        self._image_label.setPixmap(
            self._pixmap_original.scaled(
                area,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def cubrir_padre(self) -> None:
        """Ajusta la geometría para cubrir todo el widget padre."""
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

    # ── Eventos ────────────────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:  # noqa: N802 — API de Qt
        super().resizeEvent(event)
        self._reescalar_pixmap()

    def mousePressEvent(self, event) -> None:  # noqa: N802 — API de Qt
        self.descartado.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802 — API de Qt
        self.descartado.emit()
