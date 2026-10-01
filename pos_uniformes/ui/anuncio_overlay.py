"""Overlay a pantalla completa que muestra un anuncio (cartelera o aviso).

Widget "tonto": sabe pintar UN anuncio (imagen o texto grande) cubriendo toda la
ventana y avisar cuando el usuario lo descarta (toca/teclea). La rotación de la
cartelera, la inactividad y qué anuncio toca los maneja `AnuncioCartelera`.

Dos modos, que ahora se ven distintos de verdad:

- **Cartelera**: se muestra al estar inactivo y rota. Se quita con cualquier
  toque, porque solo está llenando el rato.
- **Aviso con acuse** (lo que llega de Telegram): trae dos botones, «Enterada»
  y «Luego», y un toque al aire NO lo quita. Si se quitara de un roce, Daniel
  no sabría si se vio o si se le dio sin leer, y el acuse es justo el punto.
  «Luego» existe para no dejar la caja bloqueada con un cliente enfrente: el
  aviso se esconde y vuelve a salir hasta que alguien lo acuse.

El tamaño de la letra se ajusta al largo del texto: antes era fijo (64/40 px) y
un mensaje de tres renglones se salía de la pantalla sin forma de leerlo.
"""

from __future__ import annotations

from datetime import datetime, timezone

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

# Paleta cálida MAXIMODA (misma que el resto del satélite).
_BG = "#7b2d14"       # marrón/rojo de marca — fondo de anuncios de texto
_BG_AVISO = "#8f2f12" # un tono más vivo cuando es un aviso que pide acuse
_BG_IMG = "#1a1a1a"   # casi negro — fondo para imágenes (letterbox)
_TITULO = "#fdfaf6"   # crema
_MENSAJE = "#f3e9dd"
_HINT = "#e8c9a0"

# Escalones de letra según el largo del texto (px). El primero que alcanza gana.
_TITULO_ESCALONES = ((20, 72), (40, 56), (90, 40))
_TITULO_MINIMO = 32
_MENSAJE_ESCALONES = ((80, 40), (200, 32), (500, 26))
_MENSAJE_MINIMO = 20

_BOTON_STYLE = """
QPushButton {
    background-color: #fdfaf6; color: #7b2d14;
    font-size: 30px; font-weight: 800;
    border: none; border-radius: 14px; padding: 18px 44px;
}
QPushButton#luego {
    background-color: rgba(253, 250, 246, 40); color: #fdfaf6;
    font-size: 24px; font-weight: 600; padding: 16px 32px;
}
"""


def _tamano(texto: str, escalones, minimo: int) -> int:
    largo = len(texto or "")
    for limite, px in escalones:
        if largo <= limite:
            return px
    return minimo


def hace_cuanto(iso: str | None, ahora: datetime | None = None) -> str:
    """'hace 5 min' a partir del ISO que trae el cache. Vacío si no se puede.

    Un aviso sin hora se lee como si acabara de llegar; si lleva dos horas en
    la pantalla eso importa.
    """
    if not iso:
        return ""
    try:
        momento = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return ""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    ahora = ahora or datetime.now(timezone.utc)
    seg = (ahora - momento).total_seconds()
    if seg < 60:
        return "ahora"
    if seg < 3600:
        return f"hace {int(seg // 60)} min"
    if seg < 86400:
        return f"hace {int(seg // 3600)} h"
    dias = int(seg // 86400)
    return "hace 1 día" if dias == 1 else f"hace {dias} días"


class AnuncioOverlay(QWidget):
    """Cubre la ventana y pinta un anuncio.

    Señales:
        descartado — se quita (toque en cartelera, o «Luego» en un aviso).
        acusado    — alguien tocó «Enterada».
    """

    descartado = pyqtSignal()
    acusado = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("anuncioOverlay")
        self.setAutoFillBackground(True)
        # Recibe foco para capturar teclado; el mouse se maneja en mousePressEvent.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(_BOTON_STYLE)

        self._pixmap_original: QPixmap | None = None
        self._modo_imagen = False
        #: True cuando el anuncio en pantalla pide acuse: un toque al aire no lo quita.
        self._pide_acuse = False

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setScaledContents(False)

        self._kicker_label = QLabel(self)
        self._kicker_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._kicker_label.setStyleSheet(
            f"color: {_HINT}; font-size: 22px; font-weight: 700; letter-spacing: 2px;"
        )
        self._kicker_label.setVisible(False)

        self._title_label = QLabel(self)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)

        self._message_label = QLabel(self)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setWordWrap(True)

        self._hint_label = QLabel("Toca la pantalla para volver", self)
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setStyleSheet(f"color: {_HINT}; font-size: 20px;")

        self._enterada_btn = QPushButton("✅ Enterada", self)
        self._enterada_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._enterada_btn.clicked.connect(self.acusado.emit)
        self._luego_btn = QPushButton("Luego", self)
        self._luego_btn.setObjectName("luego")
        self._luego_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._luego_btn.clicked.connect(self.descartado.emit)

        self._botones = QWidget(self)
        botones_row = QHBoxLayout(self._botones)
        botones_row.setContentsMargins(0, 0, 0, 0)
        botones_row.setSpacing(16)
        botones_row.addStretch(1)
        botones_row.addWidget(self._enterada_btn)
        botones_row.addWidget(self._luego_btn)
        botones_row.addStretch(1)
        self._botones.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 32)
        layout.addStretch(1)
        layout.addWidget(self._kicker_label)
        layout.addWidget(self._image_label)
        layout.addWidget(self._title_label)
        layout.addWidget(self._message_label)
        layout.addStretch(1)
        layout.addWidget(self._botones)
        layout.addWidget(self._hint_label)

    # ── API ──────────────────────────────────────────────────────────────────

    @property
    def pide_acuse(self) -> bool:
        """True si lo que está en pantalla necesita que alguien lo acuse."""
        return self._pide_acuse

    def render_anuncio(self, anuncio: dict) -> None:
        """Pinta el anuncio dado. Usa `imagen_path` si existe; si no, texto."""
        self._pide_acuse = bool(anuncio.get("pide_acuse"))
        imagen_path = anuncio.get("imagen_path")
        pixmap = QPixmap(imagen_path) if imagen_path else QPixmap()
        if imagen_path and not pixmap.isNull():
            self._render_imagen(pixmap)
        else:
            self._render_texto(anuncio.get("titulo"), anuncio.get("mensaje"))
        self._render_cabecera_y_pie(anuncio)

    def _render_cabecera_y_pie(self, anuncio: dict) -> None:
        """La tirita de arriba, los botones y la línea de abajo según el modo."""
        cuando = hace_cuanto(anuncio.get("creado_en"))
        if self._pide_acuse:
            self._kicker_label.setText(
                f"AVISO · {cuando}" if cuando else "AVISO"
            )
            self._kicker_label.setVisible(True)
            self._botones.setVisible(True)
            self._hint_label.setText("Toca «Enterada» para que se sepa que lo leíste")
            if not self._modo_imagen:
                self.setStyleSheet(
                    _BOTON_STYLE + f"#anuncioOverlay {{ background-color: {_BG_AVISO}; }}"
                )
        else:
            self._kicker_label.setVisible(False)
            self._botones.setVisible(False)
            self._hint_label.setText("Toca la pantalla para volver")

    def _render_imagen(self, pixmap: QPixmap) -> None:
        self._modo_imagen = True
        self._pixmap_original = pixmap
        self._title_label.setVisible(False)
        self._message_label.setVisible(False)
        self._image_label.setVisible(True)
        self.setStyleSheet(_BOTON_STYLE + f"#anuncioOverlay {{ background-color: {_BG_IMG}; }}")
        self._reescalar_pixmap()

    def _render_texto(self, titulo: str | None, mensaje: str | None) -> None:
        self._modo_imagen = False
        self._pixmap_original = None
        self._image_label.setVisible(False)
        self.setStyleSheet(_BOTON_STYLE + f"#anuncioOverlay {{ background-color: {_BG}; }}")
        titulo = titulo or ""
        mensaje = mensaje or ""
        px_titulo = _tamano(titulo, _TITULO_ESCALONES, _TITULO_MINIMO)
        px_mensaje = _tamano(mensaje, _MENSAJE_ESCALONES, _MENSAJE_MINIMO)
        self._title_label.setStyleSheet(
            f"color: {_TITULO}; font-size: {px_titulo}px; font-weight: 800;"
        )
        self._message_label.setStyleSheet(f"color: {_MENSAJE}; font-size: {px_mensaje}px;")
        self._title_label.setText(titulo)
        self._title_label.setVisible(bool(titulo))
        self._message_label.setText(mensaje)
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
        # Un aviso con acuse solo se va por sus botones: si un roce lo quitara,
        # el acuse no querría decir nada.
        if self._pide_acuse:
            return
        self.descartado.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802 — API de Qt
        if self._pide_acuse:
            return
        self.descartado.emit()
