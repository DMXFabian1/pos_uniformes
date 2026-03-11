"""Vista principal de la pestaña Analitica."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QTableWidget, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_analytics_tab(window: "MainWindow") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(10)

    filters_box = QGroupBox("Periodo de analitica")
    filters_box.setObjectName("infoCard")
    filters_layout = QHBoxLayout()
    filters_layout.setSpacing(8)
    window.analytics_period_combo.clear()
    window.analytics_period_combo.addItem("Hoy", "today")
    window.analytics_period_combo.addItem("Ultimos 7 dias", "7d")
    window.analytics_period_combo.addItem("Ultimos 30 dias", "30d")
    window.analytics_period_combo.addItem("Mes actual", "month")
    window.analytics_period_combo.addItem("Manual", "manual")
    window.analytics_from_input.setCalendarPopup(True)
    window.analytics_to_input.setCalendarPopup(True)
    today = QDate.currentDate()
    window.analytics_from_input.setDate(today)
    window.analytics_to_input.setDate(today)
    window.analytics_period_combo.currentIndexChanged.connect(window._handle_analytics_period_changed)
    window.analytics_client_combo.currentIndexChanged.connect(window._handle_analytics_period_changed)
    window.analytics_from_input.dateChanged.connect(window._handle_analytics_period_changed)
    window.analytics_to_input.dateChanged.connect(window._handle_analytics_period_changed)
    filters_layout.addWidget(QLabel("Ver"))
    filters_layout.addWidget(window.analytics_period_combo)
    filters_layout.addWidget(QLabel("Desde"))
    filters_layout.addWidget(window.analytics_from_input)
    filters_layout.addWidget(QLabel("Hasta"))
    filters_layout.addWidget(window.analytics_to_input)
    filters_layout.addWidget(window.analytics_export_button)
    filters_layout.addStretch()
    filters_box.setLayout(filters_layout)
    window.analytics_export_status_label.setObjectName("analyticsLine")
    window.analytics_export_button.clicked.connect(window._handle_export_analytics)

    business_title = QLabel("Negocio")
    business_title.setObjectName("inventoryTitle")
    business_subtitle = QLabel("Ventas, caja comercial, apartados y stock critico del periodo seleccionado.")
    business_subtitle.setObjectName("inventorySubtitle")

    business_box = QGroupBox("Negocio")
    business_box.setObjectName("infoCard")
    business_layout = QVBoxLayout()
    business_layout.setSpacing(10)

    business_kpi_grid = QGridLayout()
    business_kpi_grid.setHorizontalSpacing(12)
    business_kpi_grid.setVerticalSpacing(10)
    business_kpi_grid.addWidget(
        window._create_kpi_card(
            "Ingreso del periodo",
            window.analytics_sales_value,
            "Ventas confirmadas",
        ),
        0,
        0,
    )
    business_kpi_grid.addWidget(
        window._create_kpi_card(
            "Tickets",
            window.analytics_tickets_value,
            "Documentos confirmados",
        ),
        0,
        1,
    )
    business_kpi_grid.addWidget(
        window._create_kpi_card(
            "Promedio por venta",
            window.analytics_average_value,
            "Ticket promedio",
        ),
        0,
        2,
    )
    business_kpi_grid.addWidget(
        window._create_kpi_card(
            "Unidades vendidas",
            window.analytics_units_value,
            "Piezas del periodo",
        ),
        0,
        3,
    )
    for column in range(4):
        business_kpi_grid.setColumnStretch(column, 1)

    payments_box = QGroupBox("Metodos de pago")
    payments_box.setObjectName("infoCard")
    payments_layout = QVBoxLayout()
    payments_layout.setSpacing(8)
    window.analytics_payment_table.setColumnCount(3)
    window.analytics_payment_table.setHorizontalHeaderLabels(["Metodo", "Ventas", "Monto"])
    window.analytics_payment_table.setObjectName("dataTable")
    window.analytics_payment_table.verticalHeader().setVisible(False)
    window.analytics_payment_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.analytics_payment_table.setAlternatingRowColors(True)
    window.analytics_payment_table.setMinimumHeight(180)
    payments_layout.addWidget(window.analytics_payment_table)
    payments_box.setLayout(payments_layout)

    layaway_box = QGroupBox("Apartados")
    layaway_box.setObjectName("infoCard")
    layaway_layout = QGridLayout()
    layaway_layout.setSpacing(10)
    window.analytics_layaway_active_label.setObjectName("analyticsFlagCard")
    window.analytics_layaway_balance_label.setObjectName("analyticsFlagCard")
    window.analytics_layaway_overdue_label.setObjectName("analyticsFlagCard")
    window.analytics_layaway_delivered_label.setObjectName("analyticsFlagCard")
    layaway_layout.addWidget(window.analytics_layaway_active_label, 0, 0)
    layaway_layout.addWidget(window.analytics_layaway_balance_label, 0, 1)
    layaway_layout.addWidget(window.analytics_layaway_overdue_label, 1, 0)
    layaway_layout.addWidget(window.analytics_layaway_delivered_label, 1, 1)
    layaway_box.setLayout(layaway_layout)

    top_products_box = QGroupBox("Productos mas vendidos")
    top_products_box.setObjectName("infoCard")
    top_products_layout = QVBoxLayout()
    top_products_layout.setSpacing(8)
    window.top_products_table.setColumnCount(4)
    window.top_products_table.setHorizontalHeaderLabels(
        ["SKU", "Producto", "Unidades vendidas", "Ingreso"]
    )
    window.top_products_table.setObjectName("dataTable")
    window.top_products_table.verticalHeader().setVisible(False)
    window.top_products_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.top_products_table.setAlternatingRowColors(True)
    window.top_products_table.setMinimumHeight(220)
    top_products_layout.addWidget(window.top_products_table)
    top_products_box.setLayout(top_products_layout)

    top_clients_box = QGroupBox("Top clientes")
    top_clients_box.setObjectName("infoCard")
    top_clients_layout = QVBoxLayout()
    top_clients_layout.setSpacing(8)
    window.analytics_clients_table.setColumnCount(4)
    window.analytics_clients_table.setHorizontalHeaderLabels(["Cliente", "Codigo", "Ventas", "Monto"])
    window.analytics_clients_table.setObjectName("dataTable")
    window.analytics_clients_table.verticalHeader().setVisible(False)
    window.analytics_clients_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.analytics_clients_table.setAlternatingRowColors(True)
    window.analytics_clients_table.setMinimumHeight(220)
    top_clients_layout.addWidget(window.analytics_clients_table)
    top_clients_box.setLayout(top_clients_layout)

    stock_box = QGroupBox("Stock critico")
    stock_box.setObjectName("infoCard")
    stock_layout = QVBoxLayout()
    stock_layout.setSpacing(8)
    window.analytics_stock_table.setColumnCount(5)
    window.analytics_stock_table.setHorizontalHeaderLabels(["SKU", "Producto", "Stock", "Apartado", "Estado"])
    window.analytics_stock_table.setObjectName("dataTable")
    window.analytics_stock_table.verticalHeader().setVisible(False)
    window.analytics_stock_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    window.analytics_stock_table.setAlternatingRowColors(True)
    window.analytics_stock_table.setMinimumHeight(220)
    stock_layout.addWidget(window.analytics_stock_table)
    stock_box.setLayout(stock_layout)

    lower_grid = QGridLayout()
    lower_grid.setSpacing(12)
    lower_grid.addWidget(payments_box, 0, 0)
    lower_grid.addWidget(layaway_box, 0, 1)
    lower_grid.addWidget(top_products_box, 1, 0)
    lower_grid.addWidget(top_clients_box, 1, 1)
    lower_grid.addWidget(stock_box, 2, 0, 1, 2)
    lower_grid.setColumnStretch(0, 1)
    lower_grid.setColumnStretch(1, 1)

    business_layout.addLayout(business_kpi_grid)
    business_layout.addLayout(lower_grid)
    business_box.setLayout(business_layout)

    clients_title = QLabel("Clientes")
    clients_title.setObjectName("inventoryTitle")
    clients_subtitle = QLabel("Seguimiento comercial y base para fidelizacion futura.")
    clients_subtitle.setObjectName("inventorySubtitle")

    clients_box = QGroupBox("Clientes")
    clients_box.setObjectName("infoCard")
    clients_layout = QVBoxLayout()
    clients_layout.setSpacing(10)

    client_filter_row = QHBoxLayout()
    client_filter_row.setSpacing(8)
    client_filter_row.addWidget(QLabel("Cliente"))
    client_filter_row.addWidget(window.analytics_client_combo, 1)
    client_filter_row.addStretch()

    client_kpi_grid = QGridLayout()
    client_kpi_grid.setHorizontalSpacing(12)
    client_kpi_grid.setVerticalSpacing(10)
    client_kpi_grid.addWidget(
        window._create_kpi_card(
            "Ventas identificadas",
            window.analytics_identified_sales_value,
            "Con cliente ligado",
        ),
        0,
        0,
    )
    client_kpi_grid.addWidget(
        window._create_kpi_card(
            "Ingreso identificado",
            window.analytics_identified_income_value,
            "Ventas con cliente",
        ),
        0,
        1,
    )
    client_kpi_grid.addWidget(
        window._create_kpi_card(
            "Clientes recurrentes",
            window.analytics_repeat_clients_value,
            "Mas de una compra",
        ),
        0,
        2,
    )
    client_kpi_grid.addWidget(
        window._create_kpi_card(
            "Promedio por cliente",
            window.analytics_average_client_value,
            "Ingreso por cliente identificado",
        ),
        0,
        3,
    )
    for column in range(4):
        client_kpi_grid.setColumnStretch(column, 1)

    clients_layout.addLayout(client_filter_row)
    clients_layout.addLayout(client_kpi_grid)
    clients_layout.addWidget(top_clients_box)
    clients_box.setLayout(clients_layout)

    layout.addWidget(filters_box)
    layout.addWidget(window.analytics_export_status_label)
    layout.addWidget(business_title)
    layout.addWidget(business_subtitle)
    layout.addWidget(business_box)
    layout.addWidget(clients_title)
    layout.addWidget(clients_subtitle)
    layout.addWidget(clients_box)
    widget.setLayout(layout)
    return widget
