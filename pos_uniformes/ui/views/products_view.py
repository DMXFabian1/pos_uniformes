"""Vista principal de la pestaña Productos."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_products_tab(window: "MainWindow") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(10)

    window.catalog_table.setColumnCount(9)
    window.catalog_table.setHorizontalHeaderLabels(
        [
            "SKU",
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
    summary_layout.setSpacing(8)
    window.products_selection_label.setObjectName("analyticsLine")
    window.catalog_permission_label.setObjectName("subtleLine")
    window.catalog_layaway_filter_combo.clear()
    window.catalog_layaway_filter_combo.addItem("Apartados: todos", "")
    window.catalog_layaway_filter_combo.addItem("Solo apartados", "reserved")
    window.catalog_layaway_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed)

    window.catalog_search_input.setPlaceholderText("Buscar por SKU, marca, producto, talla o color")
    window.catalog_search_input.setClearButtonEnabled(True)
    window.catalog_search_input.setObjectName("inventoryFilterInput")
    window.catalog_category_filter_combo.setObjectName("inventoryFilterCombo")
    window.catalog_brand_filter_combo.setObjectName("inventoryFilterCombo")
    window.catalog_status_filter_combo.setObjectName("inventoryFilterCombo")
    window.catalog_layaway_filter_combo.setObjectName("inventoryFilterCombo")
    window.catalog_status_filter_combo.clear()
    window.catalog_status_filter_combo.addItem("Estado: todos", "")
    window.catalog_status_filter_combo.addItem("Activas", "active")
    window.catalog_status_filter_combo.addItem("Inactivas", "inactive")

    search_label = QLabel("Buscar")
    category_label = QLabel("Categoria")
    brand_label = QLabel("Marca")
    status_label = QLabel("Estado")
    layaway_label = QLabel("Apartados")
    for label in (search_label, category_label, brand_label, status_label, layaway_label):
        label.setObjectName("inventoryFilterLabel")

    filters_grid = QGridLayout()
    filters_grid.setHorizontalSpacing(8)
    filters_grid.setVerticalSpacing(6)
    filters_grid.addWidget(search_label, 0, 0)
    filters_grid.addWidget(window.catalog_search_input, 0, 1, 1, 3)
    filters_grid.addWidget(category_label, 0, 4)
    filters_grid.addWidget(window.catalog_category_filter_combo, 0, 5)
    filters_grid.addWidget(brand_label, 1, 0)
    filters_grid.addWidget(window.catalog_brand_filter_combo, 1, 1)
    filters_grid.addWidget(status_label, 1, 2)
    filters_grid.addWidget(window.catalog_status_filter_combo, 1, 3)
    filters_grid.addWidget(layaway_label, 1, 4)
    filters_grid.addWidget(window.catalog_layaway_filter_combo, 1, 5)
    filters_grid.setColumnStretch(1, 1)
    filters_grid.setColumnStretch(3, 1)
    filters_grid.setColumnStretch(5, 1)

    window.catalog_search_input.textChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_category_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_brand_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed)
    window.catalog_status_filter_combo.currentIndexChanged.connect(window._handle_catalog_filters_changed)

    summary_layout.addLayout(filters_grid)
    summary_layout.addWidget(window.products_selection_label)
    summary_layout.addWidget(window.catalog_permission_label)
    summary_box.setLayout(summary_layout)
    window.products_quick_setup_box = None

    layout.addWidget(summary_box)
    layout.addWidget(window.catalog_table, 1)
    widget.setLayout(layout)
    return widget
