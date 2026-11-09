"""Los avisos (QMessageBox) con la cara del programa (2026-11-07).

Daniel, con la captura de «Etiqueta enviada»: «hay que mejorar estos diálogos,
se ven muy mal estéticamente». Lo que se veía mal:

- Un hueco enorme entre el ícono y el texto. La hoja de estilos ponía
  `QMessageBox QLabel { min-width: 320px }`, y el ícono TAMBIÉN es un QLabel:
  medía 320 px de ancho con el dibujo pegado a la izquierda.
- El ícono del sistema (el globito gris de macOS, el de Windows 95 en Windows).
- Todo el texto del mismo tamaño: «Se envió…» pesaba lo mismo que «Modo:».
- El botón principal igual que los demás.

Hay ~700 `QMessageBox.information/warning/critical/question` en el programa;
cambiarlos uno por uno no tiene sentido. Un filtro de eventos instalado en la
QApplication los arregla todos al mostrarse:

- Ícono propio: un círculo de color con su signo (✓ listo, i aviso, ! cuidado,
  × falló, ? pregunta).
- El primer párrafo como título; los renglones «Clave: valor» como una ficha
  (la clave en gris, el valor en negritas); lo demás como texto normal.
- El botón por defecto en vino.

Si algo sale raro, el aviso se queda como estaba: esto nunca puede impedir
que se lea un mensaje.
"""

from __future__ import annotations

import html
import logging
import re

from PyQt6.QtCore import QEvent, QObject, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox

logger = logging.getLogger(__name__)

VINO = "#6b1f3a"
TINTA = "#2c2a27"
GRIS = "#7a6f63"
CREMA = "#f6f0e6"

#: (fondo del círculo, color del signo, signo)
_ESTILOS_ICONO = {
    "listo": ("#e3f1e6", "#2f7d4f", "✓"),
    "info": ("#f1e3e8", VINO, "i"),
    "cuidado": ("#fbefd5", "#a86a00", "!"),
    "fallo": ("#f8e1df", "#b3261e", "×"),
    "pregunta": ("#f1e3e8", VINO, "?"),
}

#: Un aviso «información» que en realidad dice que algo salió bien.
_PALABRAS_DE_LISTO = re.compile(
    r"\b(se envi(?:ó|o|aron)|enviad[oa]s?|listo|lista|guardad[oa]s?|registrad[oa]s?|hecho|cread[oa]s?|"
    r"actualizad[oa]s?|impres[oa]s?|aplicad[oa]s?|exportad[oa]s?|copiad[oa]s?|quedó|quedaron|"
    r"terminad[oa]|completad[oa]|correctamente|con éxito)\b",
    re.IGNORECASE,
)

_CSS = f"""
QMessageBox {{
    background: {CREMA};
}}
QMessageBox QLabel {{
    color: {TINTA};
    background: transparent;
    border: none;
    min-width: 0px;
}}
QLabel#qt_msgbox_label {{
    font-size: 14px;
    font-weight: 400;
}}
QLabel#qt_msgbox_informativelabel {{
    color: {GRIS};
    font-size: 13px;
}}
QMessageBox QPushButton {{
    min-width: 110px;
    min-height: 38px;
    padding: 6px 18px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 700;
    background: #fbf7f1;
    color: #73341c;
    border: 1px solid #ddd0c0;
}}
QMessageBox QPushButton:hover {{
    background: #f1e6d6;
}}
QMessageBox QPushButton:default {{
    background: {VINO};
    color: white;
    border: 1px solid {VINO};
}}
QMessageBox QPushButton:default:hover {{
    background: #82284a;
}}
"""


def tipo_de_aviso(icono: QMessageBox.Icon, titulo: str, texto: str) -> str | None:
    if icono == QMessageBox.Icon.Critical:
        return "fallo"
    if icono == QMessageBox.Icon.Warning:
        return "cuidado"
    if icono == QMessageBox.Icon.Question:
        return "pregunta"
    if icono == QMessageBox.Icon.Information:
        return "listo" if _PALABRAS_DE_LISTO.search(f"{titulo}\n{texto}") else "info"
    return None


_LADO = 44


def dibujar_icono(tipo: str, lado: int = _LADO) -> QPixmap:
    fondo, color, signo = _ESTILOS_ICONO[tipo]
    escala = 2.0
    pantalla = QGuiApplication.primaryScreen()
    if pantalla is not None:
        escala = max(1.0, pantalla.devicePixelRatio())
    px = QPixmap(int(lado * escala), int(lado * escala))
    px.setDevicePixelRatio(escala)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(fondo))
    p.drawEllipse(QRectF(0, 0, lado, lado))
    p.setBrush(QColor(color))
    p.drawEllipse(QPointF(lado / 2, lado / 2), lado * 0.34, lado * 0.34)
    fuente = QFont()
    fuente.setBold(True)
    fuente.setPixelSize(int(lado * (0.42 if signo in "✓×" else 0.4)))
    if signo == "i":
        fuente.setFamily("Georgia")
    p.setFont(fuente)
    p.setPen(QColor("white"))
    p.drawText(QRectF(0, -1, lado, lado), Qt.AlignmentFlag.AlignCenter, signo)
    p.end()
    return px


_CLAVE_VALOR = re.compile(r"^\s*([^:\n]{1,40}):\s+(.+)$")


def texto_como_html(texto: str) -> str:
    """Primer párrafo = título; «Clave: valor» = ficha; lo demás normal."""
    parrafos = [p.strip("\n") for p in re.split(r"\n\s*\n", texto.strip()) if p.strip()]
    if not parrafos:
        return html.escape(texto)
    partes = [
        f'<p style="font-size:16px; font-weight:700; margin:0 0 8px 0;">'
        f'{html.escape(parrafos[0]).replace(chr(10), "<br>")}</p>'
    ]
    for parrafo in parrafos[1:]:
        lineas = parrafo.split("\n")
        if all(_CLAVE_VALOR.match(l) for l in lineas):
            filas = "".join(
                f'<tr><td style="color:{GRIS}; font-weight:400; padding:2px 14px 2px 0;">{html.escape(m.group(1))}</td>'
                f'<td style="font-weight:700; padding:2px 0;">{html.escape(m.group(2))}</td></tr>'
                for m in (_CLAVE_VALOR.match(l) for l in lineas)
            )
            partes.append(f'<table cellspacing="0" style="margin:2px 0 6px 0;">{filas}</table>')
        else:
            partes.append(
                f'<p style="font-weight:400; margin:0 0 8px 0;">{html.escape(parrafo).replace(chr(10), "<br>")}</p>'
            )
    return "".join(partes)


def _parece_html(texto: str) -> bool:
    return bool(re.search(r"<(b|i|br|p|table|span|div|ul|li|a)\b", texto or "", re.IGNORECASE))


def poner_estilo(caja: QMessageBox) -> None:
    """Va en el Polish, antes de que el aviso calcule su tamaño: puesto en el
    Show, el ícono y el texto se medían con el estilo viejo y salían
    recortados."""
    if caja.property("_aviso_estilo"):
        return
    caja.setProperty("_aviso_estilo", True)
    caja.setStyleSheet(_CSS + (caja.styleSheet() or ""))


def embellecer(caja: QMessageBox) -> None:
    if caja.property("_aviso_bonito"):
        return
    caja.setProperty("_aviso_bonito", True)
    poner_estilo(caja)
    texto = caja.text() or ""
    tipo = tipo_de_aviso(caja.icon(), caja.windowTitle(), texto)
    if tipo is not None:
        caja.setIconPixmap(dibujar_icono(tipo))
    if texto and caja.textFormat() != Qt.TextFormat.RichText and not _parece_html(texto):
        caja.setTextFormat(Qt.TextFormat.RichText)
        caja.setText(texto_como_html(texto))
    etiqueta = caja.findChild(QLabel, "qt_msgbox_label")
    if etiqueta is not None:
        etiqueta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        etiqueta.setWordWrap(True)
    for boton in caja.buttons():
        boton.ensurePolished()
        boton.setMinimumWidth(boton.sizeHint().width())
    icono = caja.findChild(QLabel, "qt_msgboxex_icon_label")
    if icono is not None and tipo is not None:
        icono.setFixedSize(_LADO + 10, _LADO + 4)
        icono.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)


class _FiltroDeAvisos(QObject):
    def eventFilter(self, obj, evento):  # noqa: N802
        if evento.type() == QEvent.Type.Polish and isinstance(obj, QMessageBox):
            try:
                poner_estilo(obj)
            except Exception:  # noqa: BLE001
                logger.exception("No se pudo dar estilo a un aviso")
        elif evento.type() == QEvent.Type.Show and isinstance(obj, QMessageBox):
            try:
                embellecer(obj)
            except Exception:  # noqa: BLE001 — el aviso se ve como antes, pero se ve
                logger.exception("No se pudo embellecer un aviso")
        return False


def instalar(app: QApplication | None = None) -> QObject | None:
    app = app or QApplication.instance()
    if app is None:
        return None
    filtro = _FiltroDeAvisos(app)  # parent=app: no se lo lleva el recolector
    app.installEventFilter(filtro)
    return filtro
