"""Combos de «Más filtros» que no pierden su rótulo y enseñan su flecha.

Los combos de Inventario los crea la ventana como `QComboBox` comunes, y el
tema global quita la flecha (`QComboBox::drop-down` sin imagen). Este filtro
de eventos los pinta igual que siempre (fondo y borde de la hoja `invCombo`),
pero con el texto «Hay: En negativo» en vez de «En negativo» y una flecha
café a la derecha, como los filtros de la fila principal.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPolygonF
from PyQt6.QtWidgets import QComboBox, QStyle, QStyleOptionComboBox, QStylePainter

from pos_uniformes.services.inventario_vista_service import texto_combo_con_rotulo
from pos_uniformes.ui.styles.inventario_styles import CAFE

#: Lugar de la flecha y lo que se le suma al ancho del texto más largo.
_FLECHA_DERECHA = 12
_HOLGURA = 46


def texto_visible(combo: QComboBox) -> str:
    """Lo que se lee en el combo cerrado: «Hay: En negativo» o «Hay: todas»."""
    return texto_combo_con_rotulo(combo.itemText(0), combo.currentText(), combo.currentIndex())


class RotuloCombos(QObject):
    """Filtro de eventos que pinta los combos con su rótulo y su flecha."""

    def vigilar(self, combo: QComboBox) -> None:
        combo.installEventFilter(self)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:  # noqa: N802 - API de Qt
        if not isinstance(objeto, QComboBox):
            return False
        if evento.type() in (QEvent.Type.Show, QEvent.Type.Polish, QEvent.Type.FontChange):
            _ajustar_ancho(objeto)
        elif evento.type() == QEvent.Type.Paint:
            _pintar(objeto)
            return True
        return False


def _ajustar_ancho(combo: QComboBox) -> None:
    metricas = combo.fontMetrics()
    rotulo = combo.itemText(0)
    ancho = max(
        (metricas.horizontalAdvance(texto_combo_con_rotulo(rotulo, combo.itemText(i), i)) for i in range(combo.count())),
        default=0,
    )
    combo.setMinimumWidth(ancho + _HOLGURA)


def _pintar(combo: QComboBox) -> None:
    pintor = QStylePainter(combo)
    opcion = QStyleOptionComboBox()
    combo.initStyleOption(opcion)
    opcion.currentText = texto_visible(combo)
    pintor.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opcion)
    pintor.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opcion)
    x = combo.rect().right() - _FLECHA_DERECHA
    y = combo.rect().center().y()
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QColor(CAFE if combo.isEnabled() else "#b4aba0"))
    pintor.drawPolygon(QPolygonF([QPointF(x - 4, y - 2), QPointF(x + 4, y - 2), QPointF(x, y + 3)]))
    pintor.end()
