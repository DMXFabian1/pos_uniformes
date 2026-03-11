"""Vista principal de la pestaña Inventario."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QStyle,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_inventory_tab(window: "MainWindow") -> QWidget:
    widget = QWidget()
    outer_layout = QVBoxLayout()
    outer_layout.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll_content = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(10)

    actions_box = QGroupBox("Acciones rapidas")
    actions_box.setObjectName("infoCard")
    actions_layout = QVBoxLayout()
    actions_layout.setSpacing(6)
    window.catalog_selection_label.setObjectName("analyticsLine")
    window.inventory_permission_label.setStyleSheet("color: #a85b00;")
    window.inventory_new_button.setText("Nuevo")
    window.inventory_edit_button.setText("Editar")
    window.inventory_stock_button.setText("Stock")
    window.inventory_more_button.setText("Mas")
    window.toggle_product_button.setText("Prod.")
    window.toggle_variant_button.setText("Pres.")
    window.delete_product_button.setText("Eliminar prod.")
    window.delete_variant_button.setText("Eliminar pres.")
    window.purchase_button.setText("Registrar entrada")
    window.inventory_count_button.setText("Conteo fisico")
    window.inventory_adjust_button.setText("Corregir stock")
    window.inventory_generate_all_qr_button.setText("QR lote")

    grouped_buttons = {
        window.inventory_new_button: QStyle.StandardPixmap.SP_FileDialogNewFolder,
        window.inventory_edit_button: QStyle.StandardPixmap.SP_FileDialogDetailedView,
        window.inventory_stock_button: QStyle.StandardPixmap.SP_ArrowUp,
        window.inventory_more_button: QStyle.StandardPixmap.SP_TitleBarUnshadeButton,
    }
    for button, icon in grouped_buttons.items():
        button.setObjectName("inventoryMenuButton" if button is not window.inventory_more_button else "inventoryMenuSecondaryButton")
        button.setIcon(window.style().standardIcon(icon))
        button.setIconSize(QSize(16, 16))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setMinimumWidth(108 if button is not window.inventory_more_button else 92)
        button.setPopupMode(button.ToolButtonPopupMode.InstantPopup)

    for button in (window.toggle_product_button, window.toggle_variant_button, window.inventory_generate_qr_button):
        button.setObjectName("inventorySecondaryButton")
    for button in (window.delete_product_button, window.delete_variant_button):
        button.setObjectName("inventoryDangerButton")

    actions_layout.addWidget(window.catalog_selection_label)

    new_menu = QMenu(window)
    new_category_action = new_menu.addAction("Categoria")
    new_category_action.triggered.connect(window._handle_create_category)
    new_brand_action = new_menu.addAction("Marca")
    new_brand_action.triggered.connect(window._handle_create_brand)
    new_menu.addSeparator()
    new_product_action = new_menu.addAction("Producto")
    new_product_action.triggered.connect(window._handle_create_product)
    new_variant_action = new_menu.addAction("Presentacion")
    new_variant_action.triggered.connect(window._handle_create_variant)
    window.inventory_new_button.setMenu(new_menu)

    edit_menu = QMenu(window)
    edit_product_action = edit_menu.addAction("Editar producto")
    edit_product_action.triggered.connect(window._handle_update_product)
    edit_variant_action = edit_menu.addAction("Editar presentacion")
    edit_variant_action.triggered.connect(window._handle_update_variant)
    window.inventory_edit_button.setMenu(edit_menu)

    stock_menu = QMenu(window)
    register_entry_action = stock_menu.addAction("Registrar entrada")
    register_entry_action.triggered.connect(window._handle_purchase)
    stock_menu.addSeparator()
    physical_count_action = stock_menu.addAction("Conteo fisico")
    physical_count_action.triggered.connect(window._handle_inventory_count)
    correct_stock_action = stock_menu.addAction("Corregir stock")
    correct_stock_action.triggered.connect(window._handle_inventory_adjustment)
    window.inventory_stock_button.setMenu(stock_menu)

    more_menu = QMenu(window)
    delete_product_action = more_menu.addAction("Eliminar producto")
    delete_product_action.triggered.connect(window._handle_delete_product)
    delete_variant_action = more_menu.addAction("Eliminar presentacion")
    delete_variant_action.triggered.connect(window._handle_delete_variant)
    more_menu.addSeparator()
    qr_lote_action = more_menu.addAction("Generar QR en lote")
    qr_lote_action.triggered.connect(window._handle_generate_all_qr)
    window.inventory_more_button.setMenu(more_menu)

    toolbar = QHBoxLayout()
    toolbar.setSpacing(6)
    toolbar.addWidget(window.inventory_new_button)
    toolbar.addWidget(window.inventory_edit_button)
    toolbar.addWidget(window.inventory_stock_button)
    toolbar.addWidget(window.inventory_more_button)
    toolbar.addStretch()
    actions_layout.addLayout(toolbar)
    window.toggle_product_button.clicked.connect(window._handle_toggle_product)
    window.toggle_variant_button.clicked.connect(window._handle_toggle_variant)
    window.delete_product_button.clicked.connect(window._handle_delete_product)
    window.delete_variant_button.clicked.connect(window._handle_delete_variant)
    window.purchase_button.clicked.connect(window._handle_purchase)
    window.inventory_count_button.clicked.connect(window._handle_inventory_count)
    window.inventory_adjust_button.clicked.connect(window._handle_inventory_adjustment)
    actions_box.setLayout(actions_layout)

    side_box = QGroupBox("Seleccion actual")
    side_box.setObjectName("infoCard")
    side_box.setMaximumWidth(276)
    side_layout = QVBoxLayout()
    side_layout.setSpacing(6)
    window.inventory_overview_label.setObjectName("inventoryTitle")
    window.inventory_product_label.setObjectName("inventorySubtitle")
    window.inventory_status_badge.setObjectName("inventoryStatusBadge")
    window.inventory_stock_badge.setObjectName("inventoryStatusBadge")
    window.inventory_stock_hint_label.setObjectName("inventoryMetaCard")
    window.inventory_meta_label.setObjectName("inventoryMetaCardAlt")
    window.inventory_last_movement_label.setObjectName("inventoryMetaCardAlt")
    window.inventory_stock_hint_label.setWordWrap(True)
    window.inventory_meta_label.setWordWrap(True)
    window.inventory_last_movement_label.setWordWrap(True)
    window.qr_preview_label.setMinimumSize(132, 132)
    window.qr_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.qr_preview_label.setObjectName("qrPreview")
    window.qr_preview_info_label.setWordWrap(True)
    window.qr_preview_info_label.setObjectName("inventoryQrCaption")
    window.qr_status_label.setObjectName("inventoryQrStatus")
    window.inventory_generate_qr_button.setText("Generar QR")
    header_row = QHBoxLayout()
    header_row.setSpacing(8)
    header_text = QVBoxLayout()
    header_text.setSpacing(2)
    header_text.addWidget(window.inventory_overview_label)
    header_text.addWidget(window.inventory_product_label)
    header_row.addLayout(header_text, 1)
    header_row.addWidget(window.inventory_status_badge, 0, Qt.AlignmentFlag.AlignTop)
    header_row.addWidget(window.inventory_stock_badge, 0, Qt.AlignmentFlag.AlignTop)
    state_row = QHBoxLayout()
    state_row.setSpacing(6)
    state_row.addWidget(window.toggle_product_button)
    state_row.addWidget(window.toggle_variant_button)
    side_layout.addLayout(header_row)
    side_layout.addWidget(window.inventory_stock_hint_label)
    side_layout.addWidget(window.inventory_meta_label)
    side_layout.addWidget(window.inventory_last_movement_label)
    side_layout.addLayout(state_row)
    side_layout.addWidget(window.qr_preview_label, 0, Qt.AlignmentFlag.AlignHCenter)
    side_layout.addWidget(window.inventory_generate_qr_button)
    side_layout.addWidget(window.qr_preview_info_label)
    side_layout.addWidget(window.qr_status_label)
    window.inventory_generate_qr_button.clicked.connect(window._handle_generate_selected_qr)
    window.inventory_generate_all_qr_button.clicked.connect(window._handle_generate_all_qr)
    window.inventory_variant_combo.currentIndexChanged.connect(window._refresh_selected_qr_preview)
    side_box.setLayout(side_layout)

    window.inventory_table.setColumnCount(8)
    window.inventory_table.setHorizontalHeaderLabels(
        ["SKU", "Producto", "Talla", "Color", "Stock", "Apartado", "Estado", "QR"]
    )
    window.inventory_table.setObjectName("dataTable")
    window.inventory_table.verticalHeader().setVisible(False)
    window.inventory_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.inventory_table.setAlternatingRowColors(True)
    window.inventory_table.setMinimumHeight(320)
    window.inventory_table.horizontalHeader().setStretchLastSection(True)
    window.inventory_table.itemSelectionChanged.connect(window._handle_inventory_table_selection)
    window.inventory_table.currentCellChanged.connect(lambda *_: window._handle_inventory_table_selection())
    window.inventory_table.itemDoubleClicked.connect(window._handle_inventory_table_double_click)
    window.inventory_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.inventory_table.customContextMenuRequested.connect(window._show_inventory_context_menu)

    table_box = QGroupBox("Presentaciones disponibles")
    table_box.setObjectName("infoCard")
    table_layout = QVBoxLayout()
    table_layout.setSpacing(6)
    window.inventory_search_input.setPlaceholderText("Buscar por SKU, producto, talla o color")
    window.inventory_search_input.setClearButtonEnabled(True)
    window.inventory_search_input.setObjectName("inventoryFilterInput")
    window.inventory_category_filter_combo.setObjectName("inventoryFilterCombo")
    window.inventory_brand_filter_combo.setObjectName("inventoryFilterCombo")
    window.inventory_status_filter_combo.setObjectName("inventoryFilterCombo")
    window.inventory_stock_filter_combo.setObjectName("inventoryFilterCombo")
    window.inventory_qr_filter_combo.setObjectName("inventoryFilterCombo")
    window.inventory_category_filter_combo.clear()
    window.inventory_category_filter_combo.addItem("Categoria: todas", "")
    window.inventory_brand_filter_combo.clear()
    window.inventory_brand_filter_combo.addItem("Marca: todas", "")
    window.inventory_status_filter_combo.clear()
    window.inventory_status_filter_combo.addItem("Estado: todos", "")
    window.inventory_status_filter_combo.addItem("Activas", "active")
    window.inventory_status_filter_combo.addItem("Inactivas", "inactive")
    window.inventory_stock_filter_combo.clear()
    window.inventory_stock_filter_combo.addItem("Stock: todos", "")
    window.inventory_stock_filter_combo.addItem("Agotado", "zero")
    window.inventory_stock_filter_combo.addItem("Bajo", "low")
    window.inventory_stock_filter_combo.addItem("Disponible", "available")
    window.inventory_qr_filter_combo.clear()
    window.inventory_qr_filter_combo.addItem("QR: todos", "")
    window.inventory_qr_filter_combo.addItem("Con QR", "ready")
    window.inventory_qr_filter_combo.addItem("Sin QR", "missing")
    filters_row = QGridLayout()
    filters_row.setHorizontalSpacing(6)
    filters_row.setVerticalSpacing(6)
    filters_row.addWidget(window.inventory_search_input, 0, 0, 1, 3)
    filters_row.addWidget(window.inventory_category_filter_combo, 0, 3)
    filters_row.addWidget(window.inventory_brand_filter_combo, 0, 4)
    filters_row.addWidget(window.inventory_status_filter_combo, 1, 0)
    filters_row.addWidget(window.inventory_stock_filter_combo, 1, 1)
    filters_row.addWidget(window.inventory_qr_filter_combo, 1, 2)
    filters_row.setColumnStretch(0, 1)
    counters_row = QHBoxLayout()
    counters_row.setSpacing(6)
    for counter in (
        window.inventory_out_counter,
        window.inventory_low_counter,
        window.inventory_qr_pending_counter,
        window.inventory_inactive_counter,
    ):
        counter.setObjectName("inventoryCounterChip")
        counters_row.addWidget(counter)
    counters_row.addStretch()
    table_layout.addLayout(filters_row)
    table_layout.addLayout(counters_row)
    table_layout.addWidget(QLabel("Doble clic para editar la presentacion seleccionada."))
    table_layout.addWidget(window.inventory_table)
    table_box.setLayout(table_layout)
    window.inventory_search_input.textChanged.connect(lambda _: window._handle_inventory_filters_changed())
    window.inventory_category_filter_combo.currentIndexChanged.connect(
        lambda _: window._handle_inventory_filters_changed()
    )
    window.inventory_brand_filter_combo.currentIndexChanged.connect(
        lambda _: window._handle_inventory_filters_changed()
    )
    window.inventory_status_filter_combo.currentIndexChanged.connect(
        lambda _: window._handle_inventory_filters_changed()
    )
    window.inventory_stock_filter_combo.currentIndexChanged.connect(
        lambda _: window._handle_inventory_filters_changed()
    )
    window.inventory_qr_filter_combo.currentIndexChanged.connect(
        lambda _: window._handle_inventory_filters_changed()
    )

    content_layout = QGridLayout()
    content_layout.setSpacing(10)
    content_layout.addWidget(actions_box, 0, 0, 1, 2)
    content_layout.addWidget(table_box, 1, 0)
    content_layout.addWidget(side_box, 1, 1, Qt.AlignmentFlag.AlignTop)
    content_layout.setColumnStretch(0, 5)
    content_layout.setColumnStretch(1, 2)

    layout.addLayout(content_layout)
    layout.addStretch()
    scroll_content.setLayout(layout)
    scroll.setWidget(scroll_content)
    outer_layout.addWidget(scroll)
    widget.setLayout(outer_layout)
    return widget
