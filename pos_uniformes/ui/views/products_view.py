"""Vista principal de la pestaña Productos."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from pos_uniformes.ui.helpers.search_input_helper import apply_search_suggestions

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_products_tab(window: "MainWindow") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(10)

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
    window.catalog_table.itemSelectionChanged.connect(window._handle_catalog_selection)

    summary_box = QGroupBox("Consulta de productos")
    summary_box.setObjectName("infoCard")
    summary_layout = QVBoxLayout()
    summary_layout.setSpacing(6)
    window.products_selection_label.setObjectName("analyticsLine")
    window.catalog_permission_label.setObjectName("subtleLine")
    window.catalog_results_label.setObjectName("subtleLine")
    window.catalog_active_filters_label.setObjectName("subtleLine")
    window.catalog_layaway_filter_combo.clear()
    window.catalog_layaway_filter_combo.addItem("Apartados: todos", "")
    window.catalog_layaway_filter_combo.addItem("Solo apartados", "reserved")
    window.catalog_layaway_filter_combo.addItem("Sin apartados", "free")
    window.catalog_layaway_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed)

    window.catalog_search_input.setPlaceholderText(
        "Buscar producto, color, talla, marca, escuela o SKU"
    )
    window.catalog_search_input.setClearButtonEnabled(True)
    window.catalog_search_input.setObjectName("inventoryFilterInput")
    apply_search_suggestions(window.catalog_search_input, [])
    window.catalog_category_filter_combo.setObjectName("secondaryButton")
    window.catalog_brand_filter_combo.setObjectName("secondaryButton")
    window.catalog_school_filter_combo.setObjectName("secondaryButton")
    window.catalog_type_filter_combo.setObjectName("secondaryButton")
    window.catalog_piece_filter_combo.setObjectName("secondaryButton")
    window.catalog_size_filter_combo.setObjectName("secondaryButton")
    window.catalog_color_filter_combo.setObjectName("secondaryButton")
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

    search_label = QLabel("Buscar")
    category_label = QLabel("Categoria")
    brand_label = QLabel("Marca")
    school_label = QLabel("Escuela")
    type_label = QLabel("Tipo de uniforme")
    piece_label = QLabel("Pieza")
    size_label = QLabel("Talla")
    color_label = QLabel("Color")
    status_label = QLabel("Estado")
    stock_label = QLabel("Stock")
    layaway_label = QLabel("Apartados")
    origin_label = QLabel("Origen")
    duplicate_label = QLabel("Incidencias")
    for label in (
        search_label,
        category_label,
        brand_label,
        school_label,
        type_label,
        piece_label,
        size_label,
        color_label,
        status_label,
        stock_label,
        layaway_label,
        origin_label,
        duplicate_label,
    ):
        label.setObjectName("inventoryFilterLabel")

    macro_label = QLabel("Macro uniforme")
    macro_label.setObjectName("inventoryFilterLabel")
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

    filters_grid = QGridLayout()
    filters_grid.setHorizontalSpacing(6)
    filters_grid.setVerticalSpacing(4)
    filters_grid.addWidget(search_label, 0, 0)
    filters_grid.addWidget(window.catalog_search_input, 0, 1, 1, 5)
    filters_grid.addWidget(window.catalog_clear_filters_button, 0, 6)
    filters_grid.addWidget(macro_label, 1, 0)
    filters_grid.addLayout(macro_row, 1, 1, 1, 7)
    filters_grid.addWidget(category_label, 2, 0)
    filters_grid.addWidget(window.catalog_category_filter_combo, 2, 1)
    filters_grid.addWidget(brand_label, 2, 2)
    filters_grid.addWidget(window.catalog_brand_filter_combo, 2, 3)
    filters_grid.addWidget(school_label, 2, 4)
    filters_grid.addWidget(window.catalog_school_filter_combo, 2, 5)
    filters_grid.addWidget(type_label, 2, 6)
    filters_grid.addWidget(window.catalog_type_filter_combo, 2, 7)
    filters_grid.addWidget(piece_label, 3, 0)
    filters_grid.addWidget(window.catalog_piece_filter_combo, 3, 1)
    filters_grid.addWidget(size_label, 3, 2)
    filters_grid.addWidget(window.catalog_size_filter_combo, 3, 3)
    filters_grid.addWidget(color_label, 3, 4)
    filters_grid.addWidget(window.catalog_color_filter_combo, 3, 5)
    filters_grid.addWidget(status_label, 3, 6)
    filters_grid.addWidget(window.catalog_status_filter_combo, 3, 7)
    filters_grid.addWidget(stock_label, 4, 0)
    filters_grid.addWidget(window.catalog_stock_filter_combo, 4, 1)
    filters_grid.addWidget(layaway_label, 4, 2)
    filters_grid.addWidget(window.catalog_layaway_filter_combo, 4, 3)
    filters_grid.addWidget(origin_label, 4, 4)
    filters_grid.addWidget(window.catalog_origin_filter_combo, 4, 5)
    filters_grid.addWidget(duplicate_label, 4, 6)
    filters_grid.addWidget(window.catalog_duplicate_filter_combo, 4, 7)
    filters_grid.setColumnStretch(1, 1)
    filters_grid.setColumnStretch(3, 1)
    filters_grid.setColumnStretch(5, 1)
    filters_grid.setColumnStretch(7, 1)

    window.catalog_search_input.textChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_category_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_brand_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_school_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_type_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_piece_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_size_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_color_filter_combo.selectionChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_status_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_stock_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_origin_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_duplicate_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_clear_filters_button.clicked.connect(window._handle_clear_catalog_filters)
    window.catalog_type_filter_combo.setToolTip("Filtro detallado por tipo de uniforme o tipo de prenda.")

    summary_layout.addLayout(filters_grid)
    summary_layout.addWidget(window.products_selection_label)
    summary_layout.addWidget(window.catalog_results_label)
    summary_layout.addWidget(window.catalog_active_filters_label)
    summary_layout.addWidget(window.catalog_permission_label)
    summary_box.setLayout(summary_layout)
    window.products_quick_setup_box = None

    layout.addWidget(summary_box)
    layout.addWidget(window.catalog_table, 1)
    widget.setLayout(layout)
    return widget
