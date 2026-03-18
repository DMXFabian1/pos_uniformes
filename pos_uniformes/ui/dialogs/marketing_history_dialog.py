"""Dialogo reutilizable para historial de marketing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialogButtonBox, QLabel, QTableWidget, QTableWidgetItem

from pos_uniformes.ui.helpers.marketing_history_helper import build_marketing_history_view

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def _table_item(value: object) -> QTableWidgetItem:
    item = QTableWidgetItem("" if value is None else str(value))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def build_marketing_history_dialog(
    window: "MainWindow",
    *,
    changes: list[dict[str, object]],
) -> None:
    dialog, layout = window._create_modal_dialog(
        "Historial de Marketing y promociones",
        "Consulta los ultimos cambios guardados en reglas de lealtad y descuentos por nivel.",
        width=1080,
    )
    history_view = build_marketing_history_view(changes)
    status = QLabel(history_view.status_label)
    status.setObjectName("analyticsLine")
    table = QTableWidget()
    table.setColumnCount(7)
    table.setHorizontalHeaderLabels(
        ["Fecha", "Usuario", "Rol", "Seccion", "Campo", "Valor anterior", "Valor nuevo"]
    )
    table.setObjectName("dataTable")
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.setRowCount(len(history_view.rows))

    for row_index, row in enumerate(history_view.rows):
        for column_index, value in enumerate(row.values):
            table.setItem(row_index, column_index, _table_item(value))
    table.resizeColumnsToContents()

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(status)
    layout.addWidget(table)
    layout.addWidget(buttons)
    dialog.exec()
