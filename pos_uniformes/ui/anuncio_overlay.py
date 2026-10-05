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

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Paleta cálida MAXIMODA (misma que el resto del satélite).
_BG = "#7b2d14"       # marrón/rojo de marca — fondo de anuncios de texto
_BG_AVISO = "#8f2f12" # un tono más vivo cuando es un aviso que pide acuse
_BG_IMG = "#1a1a1a"   # casi negro — fondo para imágenes (letterbox)
_TITULO = "#fdfaf6"   # crema
_MENSAJE = "#f3e9dd"
_HINT = "#e8c9a0"
#: Los hijos NO pintan fondo: con una hoja de estilo en el padre, Qt dibuja
#: cada etiqueta con su propio fondo (blanco), y el texto crema se pierde
#: sobre esas bandas — justo el mismo sintoma que el overlay transparente.
_SIN_FONDO = "background: transparent;"

# Escalones de letra según el largo del texto (px). El primero que alcanza gana.
_TITULO_ESCALONES = ((20, 72), (40, 56), (90, 40))
_TITULO_MINIMO = 32
_MENSAJE_ESCALONES = ((80, 40), (200, 32), (500, 26))
_MENSAJE_MINIMO = 20

#: Pastilla de arriba: dice de qué se trata antes de que se lea el texto.
_PILDORA_STYLE = (
    "background-color: rgba(253, 250, 246, 38);"
    "color: {color}; font-size: 20px; font-weight: 800;"
    "letter-spacing: 3px; border-radius: 18px; padding: 8px 22px;"
)

_BOTON_STYLE = """
QPushButton {
    background-color: #fdfaf6; color: #7b2d14;
    font-size: 32px; font-weight: 800;
    border: none; border-radius: 16px; padding: 22px 56px;
}
QPushButton:pressed { background-color: #e8c9a0; }
QPushButton#luego {
    background-color: transparent; color: #f3e9dd;
    font-size: 24px; font-weight: 600; padding: 20px 34px;
    border: 2px solid rgba(253, 250, 246, 90); border-radius: 16px;
}
QPushButton#luego:pressed { background-color: rgba(253, 250, 246, 30); }
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
        #: Color que pinta `paintEvent`. Nunca None: un overlay sin fondo deja
        #: ver el kiosko y el texto se pierde.
        self._color_fondo = _BG
        self.setAutoFillBackground(True)
        # Un QWidget pelado NO pinta el `background-color` de su hoja de estilo
        # a menos que se le pida con WA_StyledBackground. Sin esto el overlay
        # sale transparente: se ve el kiosko detrás y el texto crema desaparece
        # sobre el blanco de la pantalla (visto en la tienda, 02/10).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Recibe foco para capturar teclado; el mouse se maneja en mousePressEvent.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._pintar_fondo(_BG)

        self._pixmap_original: QPixmap | None = None
        self._modo_imagen = False
        #: True cuando el anuncio en pantalla pide acuse: un toque al aire no lo quita.
        self._pide_acuse = False

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setScaledContents(False)
        # Que pueda ocupar lo que le den: sin esto el layout le daba su tamaño
        # natural (el del pixmap ya escalado, o cero) y la foto salía diminuta
        # junto al texto — así se vio en la tienda el 02/10.
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._image_label.setMinimumSize(1, 1)
        self._image_label.setStyleSheet(_SIN_FONDO)

        # La pastilla va en su propia fila para que no se estire de lado a lado.
        self._kicker_label = QLabel(self)
        self._kicker_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._kicker_label.setStyleSheet(_PILDORA_STYLE.format(color=_TITULO))
        self._kicker_label.setVisible(False)
        self._kicker_fila = QWidget(self)
        _kf = QHBoxLayout(self._kicker_fila)
        _kf.setContentsMargins(0, 0, 0, 0)
        _kf.addStretch(1)
        _kf.addWidget(self._kicker_label)
        _kf.addStretch(1)
        self._kicker_fila.setObjectName("avisoKicker")
        self._kicker_fila.setStyleSheet("#avisoKicker { background: transparent; }")
        self._kicker_fila.setVisible(False)

        self._title_label = QLabel(self)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)

        self._message_label = QLabel(self)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setWordWrap(True)

        self._hint_label = QLabel("Toca la pantalla para volver", self)
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setStyleSheet(f"color: {_HINT}; font-size: 20px; {_SIN_FONDO}")

        self._enterada_btn = QPushButton("✅ Enterada", self)
        self._enterada_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._enterada_btn.clicked.connect(self.acusado.emit)
        self._luego_btn = QPushButton("Luego", self)
        self._luego_btn.setObjectName("luego")
        self._luego_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._luego_btn.clicked.connect(self.descartado.emit)

        self._botones = QWidget(self)
        self._botones.setObjectName("avisoBotones")
        botones_row = QHBoxLayout(self._botones)
        botones_row.setContentsMargins(0, 0, 0, 0)
        botones_row.setSpacing(20)
        botones_row.addStretch(1)
        botones_row.addWidget(self._enterada_btn)
        botones_row.addWidget(self._luego_btn)
        botones_row.addStretch(1)
        # Con nombre: si la regla fuera a secas, se la heredarian los botones y
        # «Enterada» perderia su fondo crema (se vio al renderizar, 02/10).
        self._botones.setStyleSheet("#avisoBotones { background: transparent; }")
        self._botones.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 48, 64, 40)
        layout.setSpacing(18)
        layout.addStretch(1)
        layout.addWidget(self._kicker_fila)
        # Factor 1 solo para la imagen: cuando hay foto se queda con el hueco,
        # y cuando no hay, un QLabel oculto no pide nada y el texto se centra.
        layout.addWidget(self._image_label, 1)
        layout.addWidget(self._title_label)
        layout.addWidget(self._message_label)
        layout.addStretch(1)
        layout.addWidget(self._botones)
        layout.addWidget(self._hint_label)
        self._layout = layout
        #: Índices de los dos addStretch, para poder apagarlos con la foto.
        self._i_stretch = (0, 5)
        self._i_imagen = 2

    def _pintar_fondo(self, color: str) -> None:
        """Deja el fondo de ese color. Lo pinta `paintEvent`, no la hoja de estilo.

        Se intentó primero con `background-color` en la hoja, y en la tienda
        salió transparente: se veía el kiosko detrás y el texto crema no se leía
        sobre el blanco. Qt solo pinta el fondo de la hoja en un QWidget pelado
        bajo condiciones que cambian entre plataformas y estilos — aquí en la
        Mac se pintaba y en el Windows de la tienda no, así que ninguna prueba
        de aquí lo iba a atrapar.

        Pintarlo a mano no depende de nada de eso. La hoja y la paleta se dejan
        puestas igual: cuestan nada y cubren el primer cuadro.
        """
        self._color_fondo = color
        self.setStyleSheet(_BOTON_STYLE + f"#anuncioOverlay {{ background-color: {color}; }}")
        paleta = self.palette()
        paleta.setColor(self.backgroundRole(), QColor(color))
        self.setPalette(paleta)
        self.update()

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
            self._render_imagen(pixmap, anuncio.get("titulo"), anuncio.get("mensaje"))
        else:
            self._render_texto(anuncio.get("titulo"), anuncio.get("mensaje"))
        self._render_cabecera_y_pie(anuncio)
        # El sonido va al final, cuando lo que se ve ya quedó armado: si algo
        # del audio truena, el recado ya está en pantalla.
        from pos_uniformes.ui.helpers.anuncio_sonido import reproducir

        reproducir(anuncio.get("sonido"))

    def _render_cabecera_y_pie(self, anuncio: dict) -> None:
        """La tirita de arriba, los botones y la línea de abajo según el modo."""
        cuando = hace_cuanto(anuncio.get("creado_en"))
        if self._pide_acuse:
            self._kicker_label.setText(f"AVISO · {cuando}" if cuando else "AVISO")
            self._kicker_label.setVisible(True)
            self._kicker_fila.setVisible(True)
            self._botones.setVisible(True)
            self._hint_label.setText("Toca «Enterada» para que se sepa que lo leíste")
            if not self._modo_imagen:
                self._pintar_fondo(_BG_AVISO)
        else:
            self._kicker_label.setVisible(False)
            self._kicker_fila.setVisible(False)
            self._botones.setVisible(False)
            self._hint_label.setText("Toca la pantalla para volver")

    def _render_imagen(self, pixmap: QPixmap, titulo=None, mensaje=None) -> None:
        """La foto manda, y el pie de foto va debajo en chico.

        Antes el modo imagen escondía el texto: quien manda una foto con pie
        («así va el aparador») escribió ese pie para que se leyera.
        """
        self._modo_imagen = True
        self._pixmap_original = pixmap
        self._image_label.setVisible(True)
        pie = " · ".join(x.strip() for x in (titulo, mensaje) if x and x.strip())
        self._title_label.setVisible(False)
        self._message_label.setText(pie)
        self._message_label.setStyleSheet(f"color: {_MENSAJE}; font-size: 30px; {_SIN_FONDO}")
        self._message_label.setVisible(bool(pie))
        self._pintar_fondo(_BG_IMG)
        self._ajustar_espaciadores(hay_imagen=True)
        self._reescalar_pixmap()

    def _render_texto(self, titulo: str | None, mensaje: str | None) -> None:
        self._modo_imagen = False
        self._pixmap_original = None
        self._image_label.setVisible(False)
        self._ajustar_espaciadores(hay_imagen=False)
        self._pintar_fondo(_BG)
        titulo = titulo or ""
        mensaje = mensaje or ""
        px_titulo = _tamano(titulo, _TITULO_ESCALONES, _TITULO_MINIMO)
        px_mensaje = _tamano(mensaje, _MENSAJE_ESCALONES, _MENSAJE_MINIMO)
        self._title_label.setStyleSheet(
            f"color: {_TITULO}; font-size: {px_titulo}px; font-weight: 800; {_SIN_FONDO}"
        )
        self._message_label.setStyleSheet(f"color: {_MENSAJE}; font-size: {px_mensaje}px; {_SIN_FONDO}")
        self._title_label.setText(titulo)
        self._title_label.setVisible(bool(titulo))
        self._message_label.setText(mensaje)
        self._message_label.setVisible(bool(mensaje))

    def _ajustar_espaciadores(self, *, hay_imagen: bool) -> None:
        """Con foto, los espaciadores no estiran: el hueco es para la imagen.

        Con `addStretch(1)` arriba y abajo más el factor 1 de la imagen, el
        sobrante se repartía en tres y a la foto le tocaba un tercio. Por eso
        salía pequeña aunque el cálculo del área fuera correcto.
        """
        for i in self._i_stretch:
            self._layout.setStretch(i, 0 if hay_imagen else 1)
        # Y al revés: sin foto, el hueco de la imagen no debe reclamar nada, o
        # el texto queda pegado arriba con un vacío debajo.
        self._layout.setStretch(self._i_imagen, 1 if hay_imagen else 0)

    def area_para_imagen(self) -> QSize:
        """Cuánto espacio le toca a la foto, medido sobre la VENTANA.

        Antes se medía sobre el QLabel, y ahí estaba el huevo y la gallina: el
        label era del tamaño de su pixmap, el pixmap se escalaba al tamaño del
        label, y el resultado era una estampilla de veinte píxeles al lado del
        texto (foto de la tienda, 02/10).

        La ventana sí tiene tamaño propio desde el principio. Se le descuenta
        lo que ocupan los botones y el pie cuando los hay, para que la foto
        llegue grande pero nunca los tape.
        """
        ancho = max(1, int(self.width() * 0.92))
        # Lo que NO es la foto: márgenes, pastilla, pie, botones y el renglón de
        # abajo. Se descuenta por partes para que la foto llegue lo más grande
        # que quepa sin tapar nada.
        fraccion = 0.72 if self._pide_acuse else 0.86
        # isVisibleTo y no isVisible: `render_anuncio` corre ANTES de `show()`
        # (la cartelera pinta y luego muestra), así que isVisible() siempre
        # sería False aquí y el pie de foto nunca se descontaría — la imagen
        # salía calculada más alta de lo que cabe.
        if self._message_label.isVisibleTo(self):
            fraccion -= 0.08
        alto = max(1, int(self.height() * fraccion))
        return QSize(ancho, alto)

    def _reescalar_pixmap(self) -> None:
        if not self._modo_imagen or self._pixmap_original is None:
            return
        area = self.area_para_imagen()
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

    def paintEvent(self, event) -> None:  # noqa: N802 — API de Qt
        """Pinta el fondo SIEMPRE, antes que nada.

        Es lo único que separa un aviso legible de un texto crema flotando
        sobre la pantalla blanca del kiosko.
        """
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(self._color_fondo))
        painter.end()
        super().paintEvent(event)

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
