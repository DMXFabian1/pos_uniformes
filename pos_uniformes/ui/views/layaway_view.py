"""Vista principal de la pestaña Apartados."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_layaway_tab(window: "MainWindow") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(10)

    actions_box = QGroupBox("Acciones de apartados")
    actions_box.setObjectName("infoCard")
    actions_layout = QVBoxLayout()
    actions_layout.setSpacing(6)
    window.layaway_status_label.setObjectName("analyticsLine")
    window.layaway_quick_alerts_label.setObjectName("analyticsLine")
    actions_row = QHBoxLayout()
    actions_row.setSpacing(6)
    actions_row.addWidget(window.layaway_create_button)
    actions_row.addWidget(window.layaway_payment_button)
    actions_row.addWidget(window.layaway_deliver_button)
    actions_row.addWidget(window.layaway_cancel_button)
    actions_row.addWidget(window.layaway_receipt_button)
    actions_row.addWidget(window.layaway_sale_ticket_button)
    actions_row.addWidget(window.layaway_whatsapp_button)
    actions_row.addStretch()
    status_row = QHBoxLayout()
    status_row.setSpacing(6)
    status_row.addWidget(window.layaway_status_label, 1)
    status_row.addWidget(window.layaway_quick_alerts_label, 1)
    actions_layout.addLayout(actions_row)
    actions_layout.addLayout(status_row)
    actions_box.setLayout(actions_layout)

    window.layaway_search_input.setPlaceholderText("Buscar por folio, cliente o telefono")
    window.layaway_state_combo.clear()
    window.layaway_state_combo.addItem("Estado: todos", "")
    window.layaway_state_combo.addItem("Activos", "ACTIVO")
    window.layaway_state_combo.addItem("Liquidados", "LIQUIDADO")
    window.layaway_state_combo.addItem("Entregados", "ENTREGADO")
    window.layaway_state_combo.addItem("Cancelados", "CANCELADO")
    window.layaway_due_combo.clear()
    window.layaway_due_combo.addItem("Vencimiento: todos", "")
    window.layaway_due_combo.addItem("Vencidos", "overdue")
    window.layaway_due_combo.addItem("Vence hoy", "today")
    window.layaway_due_combo.addItem("Proximos 7 dias", "week")
    window.layaway_due_combo.addItem("Sin fecha", "none")
    window.layaway_search_input.textChanged.connect(window._handle_layaway_filters_changed)
    window.layaway_state_combo.currentIndexChanged.connect(window._handle_layaway_filters_changed)
    window.layaway_due_combo.currentIndexChanged.connect(window._handle_layaway_filters_changed)
    window.layaway_create_button.clicked.connect(window._handle_create_layaway)
    window.layaway_payment_button.clicked.connect(window._handle_register_layaway_payment)
    window.layaway_deliver_button.clicked.connect(window._handle_deliver_layaway)
    window.layaway_cancel_button.clicked.connect(window._handle_cancel_layaway)
    window.layaway_receipt_button.clicked.connect(window._handle_view_layaway_receipt)
    window.layaway_sale_ticket_button.clicked.connect(window._handle_view_layaway_sale_ticket)
    window.layaway_whatsapp_button.clicked.connect(window._handle_open_layaway_whatsapp)

    filters_row = QHBoxLayout()
    filters_row.setSpacing(6)
    filters_row.addWidget(window.layaway_search_input, 1)
    filters_row.addWidget(window.layaway_state_combo)
    filters_row.addWidget(window.layaway_due_combo)

    window.layaway_table.setColumnCount(7)
    window.layaway_table.setHorizontalHeaderLabels(
        ["Folio", "Cliente", "Estado", "Total", "Abonado", "Saldo", "Compromiso"]
    )
    window.layaway_table.setObjectName("dataTable")
    window.layaway_table.verticalHeader().setVisible(False)
    window.layaway_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.layaway_table.setAlternatingRowColors(True)
    window.layaway_table.setMinimumHeight(460)
    window.layaway_table.horizontalHeader().setStretchLastSection(True)
    window.layaway_table.itemSelectionChanged.connect(window._handle_layaway_selection)

    table_box = QGroupBox("Apartados registrados")
    table_box.setObjectName("infoCard")
    table_layout = QVBoxLayout()
    table_layout.setSpacing(6)
    table_layout.addLayout(filters_row)
    table_layout.addWidget(window.layaway_table)
    table_box.setLayout(table_layout)

    detail_box = QGroupBox("Detalle del apartado")
    detail_box.setObjectName("infoCard")
    detail_layout = QVBoxLayout()
    detail_layout.setSpacing(6)
    window.layaway_summary_label.setObjectName("inventoryTitle")
    window.layaway_customer_label.setObjectName("inventorySubtitle")
    window.layaway_balance_label.setObjectName("inventoryMetaCard")
    window.layaway_commitment_label.setObjectName("inventoryMetaCardAlt")
    window.layaway_due_status_label.setObjectName("inventoryMetaCardAlt")
    window.layaway_notes_label.setObjectName("inventoryMetaCardAlt")
    window.layaway_notes_label.setWordWrap(True)
    window.layaway_detail_table.setColumnCount(5)
    window.layaway_detail_table.setHorizontalHeaderLabels(
        ["SKU", "Producto", "Cantidad", "Precio", "Subtotal"]
    )
    window.layaway_detail_table.setObjectName("dataTable")
    window.layaway_detail_table.verticalHeader().setVisible(False)
    window.layaway_detail_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.layaway_detail_table.setAlternatingRowColors(True)
    window.layaway_detail_table.setMinimumHeight(160)
    window.layaway_detail_table.horizontalHeader().setStretchLastSection(True)
    window.layaway_payments_table.setColumnCount(4)
    window.layaway_payments_table.setHorizontalHeaderLabels(["Fecha", "Monto", "Referencia", "Usuario"])
    window.layaway_payments_table.setObjectName("dataTable")
    window.layaway_payments_table.verticalHeader().setVisible(False)
    window.layaway_payments_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.layaway_payments_table.setAlternatingRowColors(True)
    window.layaway_payments_table.setMinimumHeight(125)
    window.layaway_payments_table.horizontalHeader().setStretchLastSection(True)

    detail_meta_grid = QGridLayout()
    detail_meta_grid.setHorizontalSpacing(6)
    detail_meta_grid.setVerticalSpacing(6)
    detail_meta_grid.addWidget(window.layaway_balance_label, 0, 0)
    detail_meta_grid.addWidget(window.layaway_commitment_label, 0, 1)
    detail_meta_grid.addWidget(window.layaway_due_status_label, 1, 0)
    detail_meta_grid.addWidget(window.layaway_notes_label, 1, 1)

    detail_layout.addWidget(window.layaway_summary_label)
    detail_layout.addWidget(window.layaway_customer_label)
    detail_layout.addLayout(detail_meta_grid)
    detail_layout.addWidget(QLabel("Presentaciones reservadas"))
    detail_layout.addWidget(window.layaway_detail_table)
    detail_layout.addWidget(QLabel("Abonos registrados"))
    detail_layout.addWidget(window.layaway_payments_table)
    detail_box.setLayout(detail_layout)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(table_box)
    splitter.addWidget(detail_box)
    splitter.setChildrenCollapsible(False)
    splitter.setStretchFactor(0, 6)
    splitter.setStretchFactor(1, 5)
    splitter.setSizes([940, 620])

    layout.addWidget(actions_box)
    layout.addWidget(splitter, 1)
    widget.setLayout(layout)
    return widget
