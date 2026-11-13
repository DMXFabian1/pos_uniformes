"""Pinta las filas de la tabla de Inventario (tanda 3).

Sin celdas pintadas de fondo: el tono va solo en el color del número «Hay»
(rojo negativo, ámbar quedan pocas, gris el cero) y una talla desactivada
lleva toda su letra en gris. El SKU va en tono tenue: es dato, no enlace.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem

from pos_uniformes.ui.helpers.inventory_table_row_helper import COLUMNA_SKU, COLUMNA_STOCK
from pos_uniformes.ui.styles.inventario_styles import COLOR_CIFRA, COLOR_FILA_APAGADA, TENUE

#: Alto de cada fila: cómodo para tocar sin perder filas a 768 px.
ALTO_FILA = 36


def _celda(valor: object) -> QTableWidgetItem:
    item = QTableWidgetItem("" if valor is None else str(valor))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def pintar_filas_inventario(tabla: QTableWidget, vistas) -> None:
    """Llena la tabla con las vistas de `build_inventory_table_row_views`."""
    tabla.verticalHeader().setDefaultSectionSize(ALTO_FILA)
    for fila, vista in enumerate(vistas):
        apagada = getattr(vista, "row_tone", None) == "muted"
        for columna, valor in enumerate(vista.values):
            item = _celda(valor)
            if apagada:
                item.setForeground(QColor(COLOR_FILA_APAGADA))
            elif columna == COLUMNA_SKU:
                item.setForeground(QColor(TENUE))
            if getattr(vista, "tooltip", None):
                item.setToolTip(vista.tooltip)
            tabla.setItem(fila, columna, item)
        for columna, aviso in getattr(vista, "cell_tooltips", ()):
            item = tabla.item(fila, columna)
            if item is not None:
                item.setToolTip(aviso)
        primera = tabla.item(fila, 0)
        if primera is not None:
            primera.setData(Qt.ItemDataRole.UserRole, vista.variant_id)
        hay = tabla.item(fila, COLUMNA_STOCK)
        if hay is not None:
            _pintar_cifra(hay, getattr(vista, "stock_tone", ""), apagada=apagada)


def _pintar_cifra(item: QTableWidgetItem, tono: str, *, apagada: bool) -> None:
    item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
    fuente = QFont(item.font())
    fuente.setBold(True)
    item.setFont(fuente)
    color = COLOR_FILA_APAGADA if apagada else COLOR_CIFRA.get(tono or "")
    if color:
        item.setForeground(QColor(color))
