"""Vista principal de la pestaña Historial."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QGridLayout, QGroupBox, QLabel, QTableWidget, QVBoxLayout, QWidget

from pos_uniformes.ui.helpers.history_filter_helper import build_history_type_options

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_history_tab(window: "MainWindow") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(10)

    filters_box = QGroupBox("Filtros de historial")
    filters_box.setObjectName("infoCard")
    filters = QGridLayout()
    filters.setHorizontalSpacing(8)
    filters.setVerticalSpacing(6)
    window.history_sku_input.setPlaceholderText("SKU o registro")
    window.history_source_combo.clear()
    window.history_source_combo.addItem("Todos", "")
    window.history_source_combo.addItem("Inventario", "inventory")
    window.history_source_combo.addItem("Catalogo", "catalog")
    window.history_entity_combo.clear()
    window.history_entity_combo.addItem("Todas", "")
    window.history_entity_combo.addItem("Presentacion", "PRESENTACION")
    window.history_entity_combo.addItem("Producto", "PRODUCTO")
    window.history_entity_combo.addItem("Marca", "MARCA")
    window.history_entity_combo.addItem("Categoria", "CATEGORIA")
    window.history_type_combo.clear()
    for label, value in build_history_type_options(""):
        window.history_type_combo.addItem(label, value)
    empty_date = QDate(2000, 1, 1)
    for field, text in (
        (window.history_from_input, "Desde"),
        (window.history_to_input, "Hasta"),
    ):
        field.setCalendarPopup(True)
        field.setDisplayFormat("yyyy-MM-dd")
        field.setMinimumDate(empty_date)
        field.setSpecialValueText(text)
        field.setDate(empty_date)
        field.setObjectName("compactDateField")
    window.history_filter_button.clicked.connect(window._handle_history_filter)
    window.history_today_button.setObjectName("toolbarSecondaryButton")
    window.history_clear_button.setObjectName("toolbarGhostButton")
    window.history_today_button.clicked.connect(window._set_history_today)
    window.history_clear_button.clicked.connect(window._clear_history_filters)
    window.history_source_combo.currentIndexChanged.connect(window._handle_history_source_changed)

    filters.addWidget(QLabel("Buscar"), 0, 0)
    filters.addWidget(window.history_sku_input, 0, 1, 1, 3)
    filters.addWidget(QLabel("Origen"), 0, 4)
    filters.addWidget(window.history_source_combo, 0, 5)
    filters.addWidget(QLabel("Entidad"), 0, 6)
    filters.addWidget(window.history_entity_combo, 0, 7)
    filters.addWidget(QLabel("Tipo"), 1, 0)
    filters.addWidget(window.history_type_combo, 1, 1)
    filters.addWidget(QLabel("Desde"), 1, 2)
    filters.addWidget(window.history_from_input, 1, 3)
    filters.addWidget(QLabel("Hasta"), 1, 4)
    filters.addWidget(window.history_to_input, 1, 5)
    filters.addWidget(window.history_today_button, 1, 6)
    filters.addWidget(window.history_clear_button, 1, 7)
    filters.addWidget(window.history_filter_button, 1, 8)
    filters.setColumnStretch(1, 1)
    filters.setColumnStretch(3, 1)
    filters.setColumnStretch(5, 1)
    filters_box.setLayout(filters)

    window.history_status_label.setObjectName("statusLine")
    window.history_status_label.setWordWrap(True)

    window.movements_table.setColumnCount(8)
    window.movements_table.setHorizontalHeaderLabels(
        ["Fecha", "Origen", "Registro", "Tipo", "Cambio", "Resultado", "Usuario", "Detalle"]
    )
    window.movements_table.setObjectName("dataTable")
    window.movements_table.verticalHeader().setVisible(False)
    window.movements_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.movements_table.setAlternatingRowColors(True)
    window.movements_table.setMinimumHeight(460)

    layout.addWidget(filters_box)
    layout.addWidget(window.history_status_label)
    layout.addWidget(window.movements_table, 1)
    widget.setLayout(layout)
    return widget
