"""Vista principal de la pestaña Presupuestos."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_quotes_tab(window: "MainWindow") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(8)

    quote_box = QGroupBox("Presupuesto rapido")
    quote_box.setObjectName("infoCard")
    quote_layout = QVBoxLayout()
    quote_layout.setSpacing(5)
    window.quote_sku_input.setPlaceholderText("Escanea o captura el SKU")
    window.quote_qty_spin.setRange(1, 100)
    window.quote_qty_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    window.quote_folio_input.setObjectName("readOnlyField")
    window.quote_client_combo.setObjectName("toolbarSelect")
    window.quote_create_client_button.setObjectName("toolbarGhostButton")
    window.quote_validity_input.setCalendarPopup(True)
    window.quote_validity_input.setDate(QDate.currentDate().addDays(15))
    window.quote_note_input.setMaximumHeight(80)
    window.quote_note_input.setPlaceholderText("Observacion o condiciones del presupuesto")
    window.quote_add_button.setObjectName("toolbarSecondaryButton")
    window.quote_save_button.setObjectName("toolbarPrimaryButton")
    window.quote_remove_button.setObjectName("toolbarSecondaryButton")
    window.quote_clear_button.setObjectName("toolbarGhostButton")
    window.quote_cancel_button.setObjectName("cashierDangerButton")
    window.quote_refresh_button.setObjectName("toolbarGhostButton")
    window.quote_total_label.setObjectName("cashierTotalValue")
    window.quote_total_meta_label.setObjectName("cashierMetaLabel")
    window.quote_summary_label.setObjectName("cashierSummaryCard")
    window.quote_status_label.setObjectName("subtleLine")

    quote_form = QGridLayout()
    quote_form.setHorizontalSpacing(6)
    quote_form.setVerticalSpacing(5)
    quote_form.addWidget(QLabel("SKU"), 0, 0)
    quote_form.addWidget(window.quote_sku_input, 0, 1)
    quote_form.addWidget(QLabel("Cantidad"), 0, 2)
    quote_form.addWidget(window.quote_qty_spin, 0, 3)
    quote_form.addWidget(QLabel("Folio"), 0, 4)
    quote_form.addWidget(window.quote_folio_input, 0, 5)
    quote_form.addWidget(QLabel("Cliente guardado"), 1, 0)
    quote_form.addWidget(window.quote_client_combo, 1, 1, 1, 3)
    quote_form.addWidget(window.quote_create_client_button, 1, 4)
    quote_form.addWidget(QLabel("Vigencia"), 2, 0)
    quote_form.addWidget(window.quote_validity_input, 2, 1)
    quote_form.addWidget(QLabel("Observacion"), 2, 2)
    quote_form.addWidget(window.quote_note_input, 2, 3, 1, 3)
    quote_form.setColumnStretch(1, 2)
    quote_form.setColumnStretch(4, 2)
    quote_form.setColumnStretch(6, 2)

    quote_actions = QHBoxLayout()
    quote_actions.setSpacing(6)
    quote_actions.addWidget(window.quote_add_button)
    quote_actions.addWidget(window.quote_save_button)
    quote_actions.addStretch()
    quote_actions.addWidget(window.quote_remove_button)
    quote_actions.addWidget(window.quote_clear_button)

    window.quote_cart_table.setColumnCount(5)
    window.quote_cart_table.setHorizontalHeaderLabels(["SKU", "Producto", "Cantidad", "Precio", "Subtotal"])
    window.quote_cart_table.setObjectName("dataTable")
    window.quote_cart_table.verticalHeader().setVisible(False)
    window.quote_cart_table.setSelectionBehavior(window.quote_cart_table.SelectionBehavior.SelectRows)
    window.quote_cart_table.setAlternatingRowColors(True)
    window.quote_cart_table.setMinimumHeight(180)

    totals_box = QFrame()
    totals_box.setObjectName("cashierTotalsCard")
    totals_layout = QVBoxLayout()
    totals_layout.setContentsMargins(12, 10, 12, 10)
    totals_layout.setSpacing(2)
    totals_layout.addWidget(window.quote_total_meta_label)
    totals_layout.addWidget(window.quote_total_label)
    totals_box.setLayout(totals_layout)

    quote_layout.addLayout(quote_form)
    quote_layout.addLayout(quote_actions)
    quote_layout.addWidget(window.quote_cart_table)
    quote_layout.addWidget(totals_box, 0, Qt.AlignmentFlag.AlignRight)
    quote_layout.addWidget(window.quote_summary_label)
    quote_box.setLayout(quote_layout)

    history_box = QGroupBox("Presupuestos recientes")
    history_box.setObjectName("infoCard")
    history_layout = QVBoxLayout()
    history_layout.setSpacing(6)
    filters_row = QHBoxLayout()
    filters_row.setSpacing(6)
    window.quote_search_input.setPlaceholderText("Buscar por folio, cliente, telefono o SKU")
    window.quote_search_input.setClearButtonEnabled(True)
    window.quote_state_combo.setObjectName("inventoryFilterCombo")
    window.quote_state_combo.clear()
    window.quote_state_combo.addItem("Estado: todos", "")
    window.quote_state_combo.addItem("Emitidos", "EMITIDO")
    window.quote_state_combo.addItem("Borradores", "BORRADOR")
    window.quote_state_combo.addItem("Cancelados", "CANCELADO")
    window.quote_state_combo.addItem("Convertidos", "CONVERTIDO")
    filters_row.addWidget(window.quote_search_input, 1)
    filters_row.addWidget(window.quote_state_combo)
    filters_row.addWidget(window.quote_refresh_button)
    filters_row.addWidget(window.quote_cancel_button)

    window.quote_table.setColumnCount(7)
    window.quote_table.setHorizontalHeaderLabels(
        ["Folio", "Cliente", "Estado", "Total", "Usuario", "Vigencia", "Fecha"]
    )
    window.quote_table.setObjectName("dataTable")
    window.quote_table.verticalHeader().setVisible(False)
    window.quote_table.setSelectionBehavior(window.quote_table.SelectionBehavior.SelectRows)
    window.quote_table.setAlternatingRowColors(True)
    window.quote_table.itemSelectionChanged.connect(window._handle_quote_selection)

    detail_box = QGroupBox("Detalle seleccionado")
    detail_box.setObjectName("infoCard")
    detail_layout = QVBoxLayout()
    detail_layout.setSpacing(6)
    window.quote_customer_label.setObjectName("inventoryTitle")
    window.quote_meta_label.setWordWrap(True)
    window.quote_meta_label.setObjectName("inventoryMetaCard")
    window.quote_notes_label.setWordWrap(True)
    window.quote_notes_label.setObjectName("inventoryMetaCardAlt")
    window.quote_detail_table.setColumnCount(5)
    window.quote_detail_table.setHorizontalHeaderLabels(["SKU", "Producto", "Cantidad", "Precio", "Subtotal"])
    window.quote_detail_table.setObjectName("dataTable")
    window.quote_detail_table.verticalHeader().setVisible(False)
    window.quote_detail_table.setSelectionBehavior(window.quote_detail_table.SelectionBehavior.SelectRows)
    window.quote_detail_table.setAlternatingRowColors(True)
    detail_layout.addWidget(window.quote_customer_label)
    detail_layout.addWidget(window.quote_meta_label)
    detail_layout.addWidget(window.quote_notes_label)
    detail_layout.addWidget(window.quote_detail_table)
    detail_box.setLayout(detail_layout)

    history_layout.addWidget(window.quote_status_label)
    history_layout.addLayout(filters_row)
    history_layout.addWidget(window.quote_table)
    history_layout.addWidget(detail_box)
    history_box.setLayout(history_layout)

    layout.addWidget(quote_box)
    layout.addWidget(history_box, 1)

    window.quote_add_button.clicked.connect(window._handle_add_quote_item)
    window.quote_sku_input.returnPressed.connect(window._handle_add_quote_item)
    window.quote_save_button.clicked.connect(window._handle_save_quote)
    window.quote_remove_button.clicked.connect(window._handle_remove_quote_item)
    window.quote_clear_button.clicked.connect(window._handle_clear_quote_cart)
    window.quote_refresh_button.clicked.connect(window._handle_quote_filters_changed)
    window.quote_cancel_button.clicked.connect(window._handle_cancel_quote)
    window.quote_create_client_button.clicked.connect(window._handle_create_quote_client)
    window.quote_search_input.textChanged.connect(window._handle_quote_filters_changed)
    window.quote_state_combo.currentIndexChanged.connect(window._handle_quote_filters_changed)

    window._reset_quote_form()
    window._refresh_quote_cart_table()
    widget.setLayout(layout)
    return widget
