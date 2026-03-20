"""Vista principal de la pestaña Resumen."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget, QHBoxLayout

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_dashboard_tab(window: "MainWindow") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(12)

    status_box = QGroupBox("Estado general")
    status_box.setObjectName("infoCard")
    status_layout = QVBoxLayout()
    status_layout.setSpacing(8)
    status_intro = QLabel("Snapshot rapido del sistema y sincronizacion actual.")
    status_intro.setObjectName("inventorySubtitle")
    window.status_label.setWordWrap(True)
    window.status_label.setMinimumHeight(42)
    status_layout.addWidget(status_intro)
    status_layout.addWidget(window.status_label)
    status_box.setLayout(status_layout)
    layout.addWidget(status_box)

    kpi_box = QGroupBox("Indicadores clave")
    kpi_box.setObjectName("infoCard")
    kpi_layout = QVBoxLayout()
    kpi_layout.setSpacing(10)

    kpi_grid = QGridLayout()
    kpi_grid.setHorizontalSpacing(12)
    kpi_grid.setVerticalSpacing(12)
    window.dashboard_users_card = window._create_kpi_card(
        "Usuarios activos",
        window.kpi_users_value,
        "Cuentas con acceso al POS",
    )
    kpi_grid.addWidget(window.dashboard_users_card, 0, 0)
    kpi_grid.addWidget(
        window._create_kpi_card(
            "Productos",
            window.kpi_products_value,
            "Consulta visible para caja",
        ),
        0,
        1,
    )
    kpi_grid.addWidget(
        window._create_kpi_card(
            "Stock total",
            window.kpi_stock_value,
            "Unidades disponibles",
        ),
        0,
        2,
    )
    kpi_grid.addWidget(
        window._create_kpi_card(
            "Ventas",
            window.kpi_sales_value,
            "Documentos registrados",
        ),
        0,
        3,
    )
    for column in range(4):
        kpi_grid.setColumnStretch(column, 1)
    kpi_layout.addLayout(kpi_grid)
    kpi_box.setLayout(kpi_layout)
    layout.addWidget(kpi_box)

    window.dashboard_help_box = None

    business_box = QGroupBox("Operacion del negocio")
    business_box.setObjectName("infoCard")
    business_layout = QVBoxLayout()
    business_layout.setSpacing(6)
    business_intro = QLabel("Resumen operativo del periodo actual.")
    business_intro.setObjectName("inventorySubtitle")
    window.analytics_label.setObjectName("inventoryMetaCard")
    window.analytics_label.setWordWrap(True)
    business_layout.addWidget(business_intro)
    business_layout.addWidget(window.analytics_label)
    business_layout.addStretch(1)
    business_box.setLayout(business_layout)

    alerts_box = QGroupBox("Alertas prioritarias")
    alerts_box.setObjectName("infoCard")
    alerts_layout = QVBoxLayout()
    alerts_layout.setSpacing(6)
    alerts_intro = QLabel("Seguimiento rapido de apartados y pendientes.")
    alerts_intro.setObjectName("inventorySubtitle")
    window.layaway_alerts_label.setObjectName("analyticsFlagCard")
    window.layaway_alerts_label.setWordWrap(True)
    alerts_layout.addWidget(alerts_intro)
    alerts_layout.addWidget(window.layaway_alerts_label)
    alerts_layout.addStretch(1)
    alerts_box.setLayout(alerts_layout)

    manual_promo_box = QGroupBox("Promos manuales")
    manual_promo_box.setObjectName("infoCard")
    manual_promo_layout = QVBoxLayout()
    manual_promo_layout.setSpacing(6)
    manual_promo_intro = QLabel("Vigila autorizaciones manuales del dia.")
    manual_promo_intro.setObjectName("inventorySubtitle")
    window.dashboard_manual_promo_label.setWordWrap(True)
    window.dashboard_manual_promo_label.setObjectName("analyticsFlagCard")
    manual_promo_layout.addWidget(manual_promo_intro)
    manual_promo_layout.addWidget(window.dashboard_manual_promo_label)
    manual_promo_layout.addStretch(1)
    manual_promo_box.setLayout(manual_promo_layout)
    window.dashboard_manual_promo_box = manual_promo_box

    side_stack = QVBoxLayout()
    side_stack.setSpacing(10)
    side_stack.addWidget(alerts_box)
    side_stack.addWidget(manual_promo_box)

    info_row = QHBoxLayout()
    info_row.setSpacing(10)
    info_row.addWidget(business_box, 3)
    info_row.addLayout(side_stack, 2)

    layout.addLayout(info_row)
    layout.addStretch()
    widget.setLayout(layout)
    return widget
