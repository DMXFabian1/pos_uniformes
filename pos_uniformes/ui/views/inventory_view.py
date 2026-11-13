"""Vista principal de la pestaña Inventario."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QMenu,
    QScrollArea,
    QStyle,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)
from pos_uniformes.ui.helpers.flow_layout import FlowLayout
from pos_uniformes.ui.helpers.inventory_help_texts import AYUDA_IMPRIMIR_ETIQUETA
from pos_uniformes.ui.helpers.inventory_table_row_helper import INVENTORY_TABLE_HEADERS
from pos_uniformes.ui.helpers.inventory_toggle_helper import etiqueta_boton_prenda, etiqueta_boton_talla

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

    actions_box = QGroupBox("Acciones rápidas")
    actions_box.setObjectName("infoCard")
    actions_layout = QVBoxLayout()
    actions_layout.setSpacing(6)
    window.catalog_selection_label.setObjectName("analyticsLine")
    window.catalog_selection_label.setVisible(False)
    window.inventory_permission_label.setObjectName("catalogSectionHint")
    window.inventory_new_button.setText("Nuevo")
    window.inventory_edit_button.setText("Editar")
    window.inventory_stock_button.setText("Existencias")
    window.inventory_labels_button.setText("Etiquetas")
    window.inventory_more_button.setText("Más")
    window.toggle_product_button.setText(etiqueta_boton_prenda(True))
    window.toggle_variant_button.setText(etiqueta_boton_talla(True))
    window.delete_product_button.setText("Eliminar prenda")
    window.delete_variant_button.setText("Eliminar talla")
    window.purchase_button.setText("Registrar entrada")
    window.inventory_count_button.setText("Conteo físico")
    window.inventory_adjust_button.setText("Corregir existencia")
    window.inventory_bulk_adjust_button.setText("Ajuste en lote")
    window.inventory_bulk_price_button.setText("Precios en lote")
    window.inventory_generate_all_qr_button.setText("Generar QR de la selección")

    grouped_buttons = {
        window.inventory_new_button: QStyle.StandardPixmap.SP_FileDialogNewFolder,
        window.inventory_edit_button: QStyle.StandardPixmap.SP_FileDialogDetailedView,
        window.inventory_stock_button: QStyle.StandardPixmap.SP_ArrowUp,
        window.inventory_labels_button: QStyle.StandardPixmap.SP_FileDialogContentsView,
        window.inventory_more_button: QStyle.StandardPixmap.SP_TitleBarUnshadeButton,
    }
    for button, icon in grouped_buttons.items():
        button.setObjectName("inventoryMenuButton" if button is not window.inventory_more_button else "inventoryMenuSecondaryButton")
        button.setIcon(window.style().standardIcon(icon))
        button.setIconSize(QSize(16, 16))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setMinimumWidth(108 if button is not window.inventory_more_button else 92)
        button.setPopupMode(button.ToolButtonPopupMode.InstantPopup)

    for button in (
        window.toggle_product_button,
        window.toggle_variant_button,
        window.inventory_print_label_button,
    ):
        button.setObjectName("inventorySecondaryButton")
    window.inventory_bulk_adjust_button.setObjectName("inventorySecondaryButton")
    window.inventory_bulk_price_button.setObjectName("inventorySecondaryButton")
    for button in (window.delete_product_button, window.delete_variant_button):
        button.setObjectName("inventoryDangerButton")

    new_menu = QMenu(window)
    new_menu.setToolTipsVisible(True)
    new_category_action = new_menu.addAction("Categoría")
    new_category_action.setToolTip("Crear una categoría nueva (p. ej. Uniformes, Accesorios)")
    new_category_action.triggered.connect(window._handle_create_category)
    new_brand_action = new_menu.addAction("Marca")
    new_brand_action.setToolTip("Crear una marca nueva (p. ej. Fertoni, Ykan)")
    new_brand_action.triggered.connect(window._handle_create_brand)
    new_menu.addSeparator()
    new_product_action = new_menu.addAction("Prenda")
    new_product_action.setToolTip("Dar de alta una prenda con su nombre, escuela, tipo y pieza")
    new_product_action.triggered.connect(window._handle_create_product)
    new_variant_action = new_menu.addAction("Talla o color")
    new_variant_action.setToolTip("Agregar una talla o color (con su precio) a una prenda que ya existe")
    new_variant_action.triggered.connect(window._handle_create_variant)
    duplicate_variant_action = new_menu.addAction("Duplicar talla")
    duplicate_variant_action.setToolTip("Usar la talla elegida como base para crear otra")
    duplicate_variant_action.triggered.connect(window._handle_duplicate_variant)
    window.inventory_new_button.setMenu(new_menu)

    edit_menu = QMenu(window)
    edit_menu.setToolTipsVisible(True)
    edit_product_action = edit_menu.addAction("Editar prenda")
    edit_product_action.setToolTip("Cambiar nombre, escuela, marca o tipo de la prenda elegida")
    edit_product_action.triggered.connect(window._handle_update_product)
    photo_action = edit_menu.addAction("Foto del modelo")
    photo_action.setToolTip("Tomar con la webcam (o elegir archivo) la foto que sale en el kiosko")
    photo_action.triggered.connect(window._handle_product_photo)
    edit_variant_action = edit_menu.addAction("Editar talla")
    edit_variant_action.setToolTip("Cambiar código, talla, color o precio de la talla elegida")
    edit_variant_action.triggered.connect(window._handle_update_variant)
    edit_menu.addSeparator()
    bulk_price_action = edit_menu.addAction("Precios en lote")
    bulk_price_action.setToolTip("Cambiar el precio de varias tallas a la vez")
    bulk_price_action.triggered.connect(window._handle_inventory_bulk_price_update)
    rebajas_action = edit_menu.addAction("Ofertas y liquidación…")
    rebajas_action.setToolTip("Poner prendas en Oferta o Liquidación: no se les suma ningún otro descuento")
    rebajas_action.triggered.connect(window._handle_open_rebajas)
    window.inventory_edit_button.setMenu(edit_menu)

    stock_menu = QMenu(window)
    stock_menu.setToolTipsVisible(True)
    register_entry_action = stock_menu.addAction("Registrar entrada")
    register_entry_action.setToolTip("Sumar la mercancía que llegó del proveedor")
    register_entry_action.triggered.connect(window._handle_purchase)
    stock_menu.addSeparator()
    physical_count_action = stock_menu.addAction("Conteo físico")
    physical_count_action.setToolTip("Contar las piezas y corregir las diferencias contra lo que dice el sistema")
    physical_count_action.triggered.connect(window._handle_inventory_count)
    correct_stock_action = stock_menu.addAction("Corregir existencia")
    correct_stock_action.setToolTip("Corregir a mano cuántas hay de una talla, con su motivo")
    correct_stock_action.triggered.connect(window._handle_inventory_adjustment)
    bulk_adjust_action = stock_menu.addAction("Ajuste en lote")
    bulk_adjust_action.setToolTip("Corregir la existencia de varias tallas a la vez")
    bulk_adjust_action.triggered.connect(window._handle_inventory_bulk_adjustment)
    window.inventory_stock_button.setMenu(stock_menu)

    labels_menu = QMenu(window)
    labels_menu.setToolTipsVisible(True)
    print_selected_action = labels_menu.addAction("Imprimir las elegidas")
    print_selected_action.setToolTip("Imprimir la etiqueta de las tallas elegidas en la tabla")
    print_selected_action.triggered.connect(window._handle_inventory_print_label)
    print_visible_action = labels_menu.addAction("Imprimir todo lo filtrado")
    print_visible_action.setToolTip("Imprimir la etiqueta de todas las tallas que quedan con los filtros puestos")
    print_visible_action.triggered.connect(window._handle_inventory_print_visible_labels)
    window.inventory_labels_button.setMenu(labels_menu)

    more_menu = QMenu(window)
    more_menu.setToolTipsVisible(True)
    delete_product_action = more_menu.addAction("Eliminar prenda")
    delete_product_action.setToolTip("Borrar para siempre la prenda y todas sus tallas (solo si nunca se movió)")
    delete_product_action.triggered.connect(window._handle_delete_product)
    delete_variant_action = more_menu.addAction("Eliminar talla")
    delete_variant_action.setToolTip("Borrar para siempre la talla elegida (solo si nunca se movió)")
    delete_variant_action.triggered.connect(window._handle_delete_variant)
    more_menu.addSeparator()
    # QR: fuera de la vista (tanda 2). La etiqueta genera su QR sola al
    # imprimir; esto queda solo para mantenimiento.
    rarely_used_menu = more_menu.addMenu("Poco usado")
    rarely_used_menu.setToolTipsVisible(True)
    qr_lote_action = rarely_used_menu.addAction("Generar QR de la selección")
    qr_lote_action.setToolTip("Guarda el QR de las tallas elegidas en la tabla (la etiqueta ya lo hace sola)")
    qr_lote_action.triggered.connect(window._handle_generate_all_qr)
    qr_missing_action = rarely_used_menu.addAction("Generar los QR que faltan")
    qr_missing_action.setToolTip("Guarda el QR de las tallas activas que aún no lo tienen en esta computadora")
    qr_missing_action.triggered.connect(window._handle_generate_missing_qr)
    qr_regen_action = rarely_used_menu.addAction("Regenerar todos los QR")
    qr_regen_action.setToolTip("Vuelve a crear el QR de todas las tallas activas (reemplaza los guardados)")
    qr_regen_action.triggered.connect(window._handle_regenerate_all_qr)
    window.inventory_more_button.setMenu(more_menu)

    window.inventory_bulk_adjust_button.setVisible(False)
    window.inventory_bulk_price_button.setVisible(False)
    toolbar = QHBoxLayout()
    toolbar.setSpacing(6)
    toolbar.addWidget(window.inventory_new_button)
    toolbar.addWidget(window.inventory_edit_button)
    toolbar.addWidget(window.inventory_stock_button)
    toolbar.addWidget(window.inventory_labels_button)
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
    window.inventory_bulk_adjust_button.clicked.connect(window._handle_inventory_bulk_adjustment)
    window.inventory_bulk_price_button.clicked.connect(window._handle_inventory_bulk_price_update)
    actions_box.setLayout(actions_layout)

    side_box = QGroupBox("Selección actual")
    side_box.setObjectName("infoCard")
    # A 1366 px el título y las dos insignias no cabían en una fila de 276 px
    # («Selecci…», «SKU000…»): ahora van en dos filas y la ficha mide 300.
    # El rediseño de la ficha (400 px) es la tanda 3.
    side_box.setMaximumWidth(300)
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
    window.inventory_print_label_button.setText("Imprimir etiqueta")
    window.inventory_overview_label.setWordWrap(True)
    window.inventory_product_label.setWordWrap(True)
    badges_row = QHBoxLayout()
    badges_row.setSpacing(6)
    badges_row.addWidget(window.inventory_status_badge)
    badges_row.addWidget(window.inventory_stock_badge)
    badges_row.addStretch()
    state_row = QVBoxLayout()
    state_row.setSpacing(6)
    state_row.addWidget(window.toggle_variant_button)
    state_row.addWidget(window.toggle_product_button)
    side_layout.addWidget(window.inventory_overview_label)
    side_layout.addWidget(window.inventory_product_label)
    side_layout.addLayout(badges_row)
    side_layout.addWidget(window.inventory_stock_hint_label)
    side_layout.addWidget(window.inventory_meta_label)
    side_layout.addWidget(window.inventory_last_movement_label)
    side_layout.addLayout(state_row)
    side_layout.addWidget(window.inventory_print_label_button)
    window.inventory_print_label_button.clicked.connect(window._handle_inventory_print_label)
    window.inventory_print_label_button.setToolTip(AYUDA_IMPRIMIR_ETIQUETA)
    window.inventory_generate_all_qr_button.clicked.connect(window._handle_generate_all_qr)
    window.inventory_variant_combo.currentIndexChanged.connect(window._refresh_inventory_selection_panel)
    side_box.setLayout(side_layout)

    window.inventory_table.setColumnCount(len(INVENTORY_TABLE_HEADERS))
    window.inventory_table.setHorizontalHeaderLabels(list(INVENTORY_TABLE_HEADERS))
    window.inventory_table.setObjectName("dataTable")
    window.inventory_table.verticalHeader().setVisible(False)
    window.inventory_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.inventory_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
    window.inventory_table.setAlternatingRowColors(True)
    window.inventory_table.setMinimumHeight(320)
    window.inventory_table.horizontalHeader().setStretchLastSection(True)
    inventory_header = window.inventory_table.horizontalHeader()
    for column_index, header in enumerate(INVENTORY_TABLE_HEADERS):
        inventory_header.setSectionResizeMode(
            column_index,
            QHeaderView.ResizeMode.Stretch if header == "Prenda" else QHeaderView.ResizeMode.ResizeToContents,
        )
    inventory_header.setStretchLastSection(False)
    window.inventory_table.itemSelectionChanged.connect(window._handle_inventory_table_selection)
    window.inventory_table.currentCellChanged.connect(lambda *_: window._handle_inventory_table_selection())
    window.inventory_table.itemDoubleClicked.connect(window._handle_inventory_table_double_click)
    window.inventory_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.inventory_table.customContextMenuRequested.connect(window._show_inventory_context_menu)
    clear_selection_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), window.inventory_table)
    clear_selection_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
    clear_selection_shortcut.activated.connect(window._clear_inventory_table_selection)

    table_box = QGroupBox("Tallas")
    table_box.setObjectName("infoCard")
    table_layout = QVBoxLayout()
    table_layout.setSpacing(5)
    window.inventory_results_label.setObjectName("catalogSummaryLine")
    window.inventory_active_filters_label.setObjectName("catalogSupportLine")
    window.inventory_pagination_label.setObjectName("catalogPagerLine")
    window.inventory_previous_page_button.setObjectName("secondaryButton")
    window.inventory_next_page_button.setObjectName("secondaryButton")
    window.inventory_search_input.setPlaceholderText(
        "Busca prenda, escuela, talla, color, marca o código"
    )
    window.inventory_search_input.setClearButtonEnabled(True)
    window.inventory_search_input.setObjectName("inventoryFilterInput")
    window.inventory_category_filter_combo.setObjectName("secondaryButton")
    window.inventory_category_filter_combo.hide()
    window.inventory_brand_filter_combo.setObjectName("secondaryButton")
    window.inventory_school_filter_combo.setObjectName("secondaryButton")
    window.inventory_type_filter_combo.setObjectName("secondaryButton")
    window.inventory_piece_filter_combo.setObjectName("secondaryButton")
    window.inventory_size_filter_combo.setObjectName("secondaryButton")
    window.inventory_color_filter_combo.setObjectName("secondaryButton")
    window.inventory_use_filter_combo.setObjectName("inventoryFilterCombo")
    window.inventory_status_filter_combo.setObjectName("inventoryFilterCombo")
    window.inventory_stock_filter_combo.setObjectName("inventoryFilterCombo")
    window.inventory_conteo_filter_combo.setObjectName("inventoryFilterCombo")
    window.inventory_precio_filter_combo.setObjectName("inventoryFilterCombo")
    window.inventory_precio_text_input.setObjectName("inventoryFilterCombo")
    window.inventory_precio_text_input.setPlaceholderText("Precio $")
    window.inventory_clear_filters_button.setObjectName("secondaryButton")
    window.inventory_clear_filters_button.setText("Quitar filtros")
    window.inventory_use_filter_combo.clear()
    window.inventory_use_filter_combo.addItem("Ropa: toda", "")
    window.inventory_use_filter_combo.addItem("Uniforme escolar", "school_only")
    window.inventory_use_filter_combo.addItem("Ropa normal", "general_only")
    window.inventory_status_filter_combo.clear()
    window.inventory_status_filter_combo.addItem("Estado: todas", "")
    window.inventory_status_filter_combo.addItem("Activas", "active")
    window.inventory_status_filter_combo.addItem("Desactivadas", "inactive")
    window.inventory_stock_filter_combo.clear()
    window.inventory_stock_filter_combo.addItem("Hay: todas", "")
    window.inventory_stock_filter_combo.addItem("En negativo", "negative")
    window.inventory_stock_filter_combo.addItem("Agotadas", "zero")
    window.inventory_stock_filter_combo.addItem("Quedan pocas", "low")
    window.inventory_stock_filter_combo.addItem("Sí hay", "available")
    window.inventory_stock_filter_combo.addItem("Bajo el mínimo", "below_min")
    window.inventory_conteo_filter_combo.clear()
    window.inventory_conteo_filter_combo.addItem("Contada: todas", "")
    window.inventory_conteo_filter_combo.addItem("Nunca contada", "never")
    window.inventory_conteo_filter_combo.addItem("Hace 0 a 3 días", "recent")
    window.inventory_conteo_filter_combo.addItem("Hace 8 días o más", "stale")
    window.inventory_precio_filter_combo.clear()
    window.inventory_precio_filter_combo.addItem("Precio: todos", "")
    window.inventory_precio_filter_combo.addItem("Hasta $99", "under_100")
    window.inventory_precio_filter_combo.addItem("$100 – $199", "100_199")
    window.inventory_precio_filter_combo.addItem("$200 – $499", "200_499")
    window.inventory_precio_filter_combo.addItem("$500+", "500_plus")
    filters_row = QGridLayout()
    filters_row.setHorizontalSpacing(6)
    filters_row.setVerticalSpacing(4)
    filters_row.addWidget(window.inventory_search_input, 0, 0, 1, 5)
    filters_row.addWidget(window.inventory_clear_filters_button, 0, 5)
    filters_row.addWidget(window.inventory_precio_text_input, 0, 6)
    filters_row.addWidget(window.inventory_use_filter_combo, 1, 0)
    filters_row.addWidget(window.inventory_brand_filter_combo, 1, 1)
    filters_row.addWidget(window.inventory_school_filter_combo, 1, 2)
    filters_row.addWidget(window.inventory_type_filter_combo, 1, 3)
    filters_row.addWidget(window.inventory_piece_filter_combo, 1, 4)
    filters_row.addWidget(window.inventory_size_filter_combo, 1, 5)
    filters_row.addWidget(window.inventory_color_filter_combo, 1, 6)
    filters_row.addWidget(window.inventory_status_filter_combo, 2, 0)
    filters_row.addWidget(window.inventory_stock_filter_combo, 2, 1)
    filters_row.addWidget(window.inventory_precio_filter_combo, 2, 2)
    filters_row.addWidget(window.inventory_conteo_filter_combo, 2, 3)
    filters_row.setColumnStretch(0, 1)
    filters_row.setColumnStretch(1, 1)
    filters_row.setColumnStretch(2, 1)
    filters_row.setColumnStretch(3, 1)
    filters_row.setColumnStretch(4, 1)
    filters_row.setColumnStretch(5, 1)
    filters_row.setColumnStretch(6, 1)
    window.inventory_active_filters_wrap.setVisible(False)
    window.inventory_active_filters_flow_layout = FlowLayout(
        window.inventory_active_filters_wrap,
        margin=0,
        h_spacing=6,
        v_spacing=6,
    )
    window.inventory_active_filters_wrap.setLayout(window.inventory_active_filters_flow_layout)
    counters_row = QHBoxLayout()
    counters_row.setSpacing(6)
    for counter in (
        window.inventory_negative_counter,
        window.inventory_out_counter,
        window.inventory_low_counter,
        window.inventory_inactive_counter,
    ):
        counter.setObjectName("inventoryCounterChip")
        counters_row.addWidget(counter)
    counters_row.addStretch()
    summary_row = QHBoxLayout()
    summary_row.setSpacing(8)
    summary_row.addStretch(1)
    summary_row.addWidget(window.inventory_pagination_label)
    summary_row.addWidget(window.inventory_previous_page_button)
    summary_row.addWidget(window.inventory_next_page_button)
    table_layout.addLayout(filters_row)
    table_layout.addWidget(window.inventory_active_filters_wrap)
    table_layout.addLayout(summary_row)
    table_layout.addLayout(counters_row)
    table_layout.addWidget(window.inventory_table)
    table_layout.addWidget(window.inventory_results_label)
    table_box.setLayout(table_layout)
    window.inventory_search_input.textChanged.connect(lambda _: window._schedule_inventory_filter_refresh_reset_page())
    window.inventory_search_input.returnPressed.connect(window._handle_inventory_filters_changed_reset_page)
    window.inventory_category_filter_combo.selectionChanged.connect(window._handle_inventory_filters_changed_reset_page)
    window.inventory_brand_filter_combo.selectionChanged.connect(window._handle_inventory_filters_changed_reset_page)
    window.inventory_school_filter_combo.selectionChanged.connect(window._handle_inventory_filters_changed_reset_page)
    window.inventory_type_filter_combo.selectionChanged.connect(window._handle_inventory_filters_changed_reset_page)
    window.inventory_piece_filter_combo.selectionChanged.connect(window._handle_inventory_filters_changed_reset_page)
    window.inventory_size_filter_combo.selectionChanged.connect(window._handle_inventory_filters_changed_reset_page)
    window.inventory_color_filter_combo.selectionChanged.connect(window._handle_inventory_filters_changed_reset_page)
    window.inventory_use_filter_combo.currentIndexChanged.connect(
        lambda _: window._handle_inventory_filters_changed_reset_page()
    )
    window.inventory_status_filter_combo.currentIndexChanged.connect(
        lambda _: window._handle_inventory_filters_changed_reset_page()
    )
    window.inventory_stock_filter_combo.currentIndexChanged.connect(
        lambda _: window._handle_inventory_filters_changed_reset_page()
    )
    window.inventory_conteo_filter_combo.currentIndexChanged.connect(
        lambda _: window._handle_inventory_filters_changed_reset_page()
    )
    window.inventory_precio_filter_combo.currentIndexChanged.connect(
        lambda _: window._handle_inventory_filters_changed_reset_page()
    )
    window.inventory_precio_text_input.textChanged.connect(
        lambda _: window._schedule_inventory_filter_refresh_reset_page()
    )
    window.inventory_clear_filters_button.clicked.connect(window._handle_clear_inventory_filters)
    window.inventory_previous_page_button.clicked.connect(window._handle_inventory_previous_page)
    window.inventory_next_page_button.clicked.connect(window._handle_inventory_next_page)

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
