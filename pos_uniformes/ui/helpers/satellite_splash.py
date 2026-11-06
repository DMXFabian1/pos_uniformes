"""La pantalla de arranque del kiosko.

Era un rectángulo crema con «Presupuestos Satélite» y un renglón chiquito al
pie («Esperando a la PC principal… (53s)») que no decía qué iba a pasar
después. Ahora lleva la marca, dice en una frase qué está haciendo, en otra
qué pasa si no resulta, y una barra para ver que no se quedó trabada
(Daniel, 2026-11-05: «mejoremos esta ventana»).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QSplashScreen

ANCHO, ALTO = 640, 380
ALTO_BANDA = 168
RADIO = 22

_VINO, _VINO_MEDIO, _TERRACOTA = "#4d1730", "#7a2438", "#c4622d"
_CREMA, _TINTA, _GRIS, _ACENTO = "#f7f0e4", "#2c2a27", "#857a6c", "#a84f2d"


def _logo_blanco(ancho: int) -> QPixmap | None:
    """El logotipo de la tienda (el del ticket), en blanco para ir sobre la banda."""
    ruta = Path(__file__).resolve().parents[2] / "assets" / "ticket" / "logo.png"
    original = QPixmap(str(ruta))
    if original.isNull():
        return None
    imagen = original.toImage().convertToFormat(original.toImage().Format.Format_ARGB32)
    # Lo oscuro del logo pasa a ser blanco opaco; lo claro, transparente.
    for y in range(imagen.height()):
        for x in range(imagen.width()):
            c = imagen.pixelColor(x, y)
            oscuridad = int((255 - c.lightness()) * c.alpha() / 255)
            imagen.setPixelColor(x, y, QColor(255, 255, 255, oscuridad))
    return QPixmap.fromImage(imagen).scaledToWidth(ancho, Qt.TransformationMode.SmoothTransformation)


def construir_fondo(version: str = "") -> QPixmap:
    """La parte que no cambia: banda con la marca arriba, cuerpo crema abajo."""
    pix = QPixmap(ANCHO, ALTO)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    silueta = QPainterPath()
    silueta.addRoundedRect(QRectF(0, 0, ANCHO, ALTO), RADIO, RADIO)
    p.setClipPath(silueta)
    p.fillRect(0, 0, ANCHO, ALTO, QColor(_CREMA))

    # Banda: el mismo vino → terracota de la cabecera del kiosko.
    degradado = QLinearGradient(0, 0, ANCHO, ALTO_BANDA)
    degradado.setColorAt(0.0, QColor(_VINO))
    degradado.setColorAt(0.6, QColor(_VINO_MEDIO))
    degradado.setColorAt(1.0, QColor(_TERRACOTA))
    p.fillRect(0, 0, ANCHO, ALTO_BANDA, degradado)

    logo = _logo_blanco(360)
    if logo is not None:
        p.drawPixmap(int((ANCHO - logo.width()) / 2), 52, logo)
    else:   # sin el archivo, la marca en letras
        f = QFont()
        f.setPointSize(34)
        f.setWeight(QFont.Weight.Black)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(0, 44, ANCHO, 60), Qt.AlignmentFlag.AlignCenter, "MAXIMODA")
    f = QFont()
    f.setPointSize(11)
    f.setWeight(QFont.Weight.DemiBold)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
    p.setFont(f)
    p.setPen(QColor(255, 255, 255, 215))
    p.drawText(QRectF(0, 112, ANCHO, 24), Qt.AlignmentFlag.AlignCenter, "KIOSKO DE LA TIENDA")

    if version:
        f = QFont()
        f.setPointSize(10)
        p.setFont(f)
        p.setPen(QColor("#b3a797"))
        p.drawText(QRectF(0, ALTO - 30, ANCHO - 26, 18),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"Versión {version}")
    p.end()
    return pix


class SplashDelKiosko(QSplashScreen):
    """Splash con mensaje, detalle y barra de avance pintados por nosotros."""

    def __init__(self, version: str = "") -> None:
        super().__init__(construir_fondo(version))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)   # esquinas redondas de verdad
        self.mensaje = ""
        self.detalle = ""
        self.avance: float | None = None

    def decir(self, mensaje: str, detalle: str = "", avance: float | None = None) -> None:
        """Qué está haciendo, qué pasa si no resulta, y cuánto lleva (0 a 1).

        `avance=None` deja la barra llena y tenue: está trabajando, sin cuenta."""
        self.mensaje, self.detalle = mensaje, detalle
        self.avance = None if avance is None else max(0.0, min(1.0, float(avance)))
        self.repaint()

    def drawContents(self, painter: QPainter) -> None:  # noqa: N802 (API de Qt)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margen = 56
        f = QFont()
        f.setPointSize(17)
        f.setWeight(QFont.Weight.Bold)
        painter.setFont(f)
        painter.setPen(QColor(_TINTA))
        painter.drawText(QRectF(margen, ALTO_BANDA + 30, ANCHO - 2 * margen, 30),
                         int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter), self.mensaje)
        f = QFont()
        f.setPointSize(12)
        painter.setFont(f)
        painter.setPen(QColor(_GRIS))
        painter.drawText(QRectF(margen, ALTO_BANDA + 64, ANCHO - 2 * margen, 40),
                         # AlignmentFlag | TextFlag no es un tipo que drawText acepte: va como entero.
                         Qt.AlignmentFlag.AlignHCenter.value | Qt.AlignmentFlag.AlignTop.value
                         | Qt.TextFlag.TextWordWrap.value,
                         self.detalle)
        # La barra: riel claro y lo avanzado en terracota.
        riel = QRectF(margen + 40, ALTO_BANDA + 122, ANCHO - 2 * (margen + 40), 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e8dccb"))
        painter.drawRoundedRect(riel, 4, 4)
        if self.avance is None:
            painter.setBrush(QColor(168, 79, 45, 90))
            painter.drawRoundedRect(riel, 4, 4)
        elif self.avance > 0:
            lleno = QRectF(riel)
            lleno.setWidth(max(8.0, riel.width() * self.avance))
            painter.setBrush(QColor(_ACENTO))
            painter.drawRoundedRect(lleno, 4, 4)
