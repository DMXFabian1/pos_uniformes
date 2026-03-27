"""Vista principal de la pestaña Productos."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QHeaderView

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_products_tab(window: "MainWindow") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(8)

    window.catalog_table.setColumnCount(12)
    window.catalog_table.setHorizontalHeaderLabels(
        [
            "SKU",
            "Escuela",
            "Tipo",
            "Pieza",
            "Marca",
            "Producto",
            "Talla",
            "Color",
            "Precio",
            "Stock",
            "Apartado",
            "Estado",
        ]
    )
    window.catalog_table.setObjectName("dataTable")
    window.catalog_table.verticalHeader().setVisible(False)
    window.catalog_table.setSelectionBehavior(window.catalog_table.SelectionBehavior.SelectRows)
    window.catalog_table.setAlternatingRowColors(True)
    window.catalog_table.setMinimumHeight(420)
    window.catalog_table.verticalHeader().setDefaultSectionSize(34)
    catalog_header = window.catalog_table.horizontalHeader()
    catalog_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    catalog_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    catalog_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    catalog_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    catalog_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    catalog_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
    catalog_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
    catalog_header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
    catalog_header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
    catalog_header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)
    catalog_header.setSectionResizeMode(10, QHeaderView.ResizeMode.ResizeToContents)
    catalog_header.setSectionResizeMode(11, QHeaderView.ResizeMode.ResizeToContents)
    catalog_header.setStretchLastSection(False)
    window.catalog_table.itemSelectionChanged.connect(window._handle_catalog_selection)

    summary_box = QGroupBox("Consulta de productos")
    summary_box.setObjectName("infoCard")
    summary_layout = QVBoxLayout()
    summary_layout.setSpacing(8)
    window.products_selection_label.setObjectName("catalogSelectionLine")
    window.catalog_permission_label.setObjectName("catalogSupportLine")
    window.catalog_results_label.setObjectName("catalogSummaryLine")
    window.catalog_active_filters_label.setObjectName("catalogSupportLine")
    window.catalog_pagination_label.setObjectName("catalogPagerLine")
    window.catalog_previous_page_button.setObjectName("secondaryButton")
    window.catalog_next_page_button.setObjectName("secondaryButton")
    window.catalog_layaway_filter_combo.clear()
    window.catalog_layaway_filter_combo.addItem("Apartados: todos", "")
    window.catalog_layaway_filter_combo.addItem("Solo apartados", "reserved")
    window.catalog_layaway_filter_combo.addItem("Sin apartados", "free")
    window.catalog_layaway_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed_reset_page)

    window.catalog_search_input.setPlaceholderText(
        "Buscar producto, color, talla, marca, escuela o SKU"
    )
    window.catalog_search_input.setClearButtonEnabled(True)
    window.catalog_search_input.setObjectName("inventoryFilterInput")
    window.catalog_category_filter_combo.setObjectName("secondaryButton")
    window.catalog_brand_filter_combo.setObjectName("secondaryButton")
    window.catalog_school_filter_combo.setObjectName("secondaryButton")
    window.catalog_type_filter_combo.setObjectName("secondaryButton")
    window.catalog_piece_filter_combo.setObjectName("secondaryButton")
    window.catalog_size_filter_combo.setObjectName("secondaryButton")
    window.catalog_color_filter_combo.setObjectName("secondaryButton")
    window.catalog_school_scope_filter_combo.setObjectName("inventoryFilterCombo")
    window.catalog_status_filter_combo.setObjectName("inventoryFilterCombo")
    window.catalog_stock_filter_combo.setObjectName("inventoryFilterCombo")
    window.catalog_layaway_filter_combo.setObjectName("inventoryFilterCombo")
    window.catalog_origin_filter_combo.setObjectName("inventoryFilterCombo")
    window.catalog_duplicate_filter_combo.setObjectName("inventoryFilterCombo")
    window.catalog_clear_filters_button.setObjectName("secondaryButton")
    window.catalog_status_filter_combo.clear()
    window.catalog_status_filter_combo.addItem("Estado: todos", "")
    window.catalog_status_filter_combo.addItem("Activas", "active")
    window.catalog_status_filter_combo.addItem("Inactivas", "inactive")
    window.catalog_stock_filter_combo.clear()
    window.catalog_stock_filter_combo.addItem("Stock: todos", "")
    window.catalog_stock_filter_combo.addItem("Con stock", "in_stock")
    window.catalog_stock_filter_combo.addItem("Sin stock", "out_of_stock")
    window.catalog_stock_filter_combo.addItem("Stock bajo (1-3)", "low_stock")
    window.catalog_stock_filter_combo.addItem("Stock > apartado", "available_over_reserved")
    window.catalog_origin_filter_combo.clear()
    window.catalog_origin_filter_combo.addItem("Origen: todos", "")
    window.catalog_origin_filter_combo.addItem("Importados", "legacy")
    window.catalog_origin_filter_combo.addItem("Nuevos", "native")
    window.catalog_duplicate_filter_combo.clear()
    window.catalog_duplicate_filter_combo.addItem("Incidencias: todas", "")
    window.catalog_duplicate_filter_combo.addItem("Solo fallbacks importados", "fallback_only")
    window.catalog_duplicate_filter_combo.addItem("Ocultar fallbacks", "fallback_exclude")
    window.catalog_school_scope_filter_combo.clear()
    window.catalog_school_scope_filter_combo.addItem("Seccion: todas", "")
    window.catalog_school_scope_filter_combo.addItem("Solo uniforme escolar", "school_only")
    window.catalog_school_scope_filter_combo.addItem("Solo ropa normal", "general_only")

    search_title = QLabel("Busqueda rapida")
    search_title.setObjectName("catalogSectionTitle")
    search_hint = QLabel("Ubica una prenda por texto, separa por seccion y entra por linea con un solo clic.")
    search_hint.setObjectName("catalogSectionHint")
    macro_row = QHBoxLayout()
    macro_row.setSpacing(6)
    for macro_type in ("Deportivo", "Oficial", "Basico", "Escolta", "Accesorio"):
        button = window.catalog_uniform_macro_buttons.get(macro_type)
        if button is None:
            button = QPushButton(macro_type)
            window.catalog_uniform_macro_buttons[macro_type] = button
            button.setObjectName("chipButton")
            button.clicked.connect(lambda _checked=False, value=macro_type: window._set_catalog_uniform_macro_filter(value))
        macro_row.addWidget(button)
    macro_row.addStretch(1)

    hero_card = QFrame()
    hero_card.setObjectName("catalogSpotlightCard")
    hero_layout = QVBoxLayout()
    hero_layout.setSpacing(8)
    hero_layout.addWidget(search_title)
    hero_layout.addWidget(search_hint)
    hero_layout.addWidget(window.products_selection_label)

    search_row = QHBoxLayout()
    search_row.setSpacing(6)
    search_row.addWidget(window.catalog_search_input, 4)
    search_row.addWidget(window.catalog_school_scope_filter_combo, 2)
    search_row.addWidget(window.catalog_clear_filters_button, 1)
    hero_layout.addLayout(search_row)

    macro_caption = QLabel("Linea rapida")
    macro_caption.setObjectName("catalogSectionCaption")
    hero_layout.addWidget(macro_caption)
    hero_layout.addLayout(macro_row)
    hero_card.setLayout(hero_layout)

    filters_card = QFrame()
    filters_card.setObjectName("catalogFiltersCard")
    filters_layout = QVBoxLayout()
    filters_layout.setSpacing(6)
    filters_title = QLabel("Filtros finos")
    filters_title.setObjectName("catalogSectionTitle")
    filters_hint = QLabel("Afina por contexto comercial, disponibilidad y origen sin saturar la tabla.")
    filters_hint.setObjectName("catalogSectionHint")
    filters_layout.addWidget(filters_title)
    filters_layout.addWidget(filters_hint)

    filters_grid = QGridLayout()
    filters_grid.setHorizontalSpacing(6)
    filters_grid.setVerticalSpacing(6)
    filters_grid.addWidget(window.catalog_category_filter_combo, 0, 0)
    filters_grid.addWidget(window.catalog_brand_filter_combo, 0, 1)
    filters_grid.addWidget(window.catalog_school_filter_combo, 0, 2)
    filters_grid.addWidget(window.catalog_type_filter_combo, 0, 3)
    filters_grid.addWidget(window.catalog_piece_filter_combo, 1, 0)
    filters_grid.addWidget(window.catalog_size_filter_combo, 1, 1)
    filters_grid.addWidget(window.catalog_color_filter_combo, 1, 2)
    filters_grid.addWidget(window.catalog_status_filter_combo, 1, 3)
    filters_grid.addWidget(window.catalog_stock_filter_combo, 2, 0)
    filters_grid.addWidget(window.catalog_layaway_filter_combo, 2, 1)
    filters_grid.addWidget(window.catalog_origin_filter_combo, 2, 2)
    filters_grid.addWidget(window.catalog_duplicate_filter_combo, 2, 3)
    for column in range(4):
        filters_grid.setColumnStretch(column, 1)
    filters_layout.addLayout(filters_grid)
    filters_card.setLayout(filters_layout)

    status_card = QFrame()
    status_card.setObjectName("catalogStatusStrip")
    status_layout = QVBoxLayout()
    status_layout.setSpacing(6)

    status_header = QHBoxLayout()
    status_header.setSpacing(8)
    status_header.addWidget(window.catalog_results_label, 1)
    status_header.addWidget(window.catalog_pagination_label)
    status_header.addWidget(window.catalog_previous_page_button)
    status_header.addWidget(window.catalog_next_page_button)
    status_layout.addLayout(status_header)
    status_card.setLayout(status_layout)

    filters_grid.setContentsMargins(0, 0, 0, 0)
    filters_grid.setColumnStretch(1, 1)

    window.catalog_search_input.textChanged.connect(lambda _: window._schedule_catalog_filter_refresh_reset_page())
    window.catalog_search_input.returnPressed.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_category_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_brand_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_school_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_type_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_piece_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_size_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_color_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_school_scope_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_status_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_stock_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_origin_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_duplicate_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed_reset_page)
    window.catalog_clear_filters_button.clicked.connect(window._handle_clear_catalog_filters)
    window.catalog_previous_page_button.clicked.connect(window._handle_catalog_previous_page)
    window.catalog_next_page_button.clicked.connect(window._handle_catalog_next_page)
    window.catalog_type_filter_combo.setToolTip("Filtro detallado por linea o tipo de prenda.")
    window.catalog_school_scope_filter_combo.setToolTip(
        "Separa rapido entre uniforme escolar y ropa normal segun la categoria real del producto."
    )

    top_cards_row = QHBoxLayout()
    top_cards_row.setSpacing(8)
    top_cards_row.addWidget(hero_card, 5)
    top_cards_row.addWidget(filters_card, 7)

    summary_layout.addLayout(top_cards_row)
    summary_layout.addWidget(status_card)
    summary_box.setLayout(summary_layout)
    window.products_quick_setup_box = None

    layout.addWidget(summary_box)
    layout.addWidget(window.catalog_table, 1)
    widget.setLayout(layout)
    return widget
