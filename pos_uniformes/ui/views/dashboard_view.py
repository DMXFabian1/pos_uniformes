"""Vista principal de la pestaña Resumen."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_dashboard_tab(window: "MainWindow") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(10)

    layout.addWidget(window.status_label)

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

    window.dashboard_help_box = None

    business_box = QGroupBox("Operacion del negocio")
    business_box.setObjectName("infoCard")
    business_layout = QVBoxLayout()
    business_layout.setSpacing(6)
    business_intro = QLabel("Resumen operativo del periodo actual.")
    business_intro.setObjectName("inventorySubtitle")
    window.analytics_label.setObjectName("inventoryMetaCard")
    business_layout.addWidget(business_intro)
    business_layout.addWidget(window.analytics_label)
    business_box.setLayout(business_layout)

    alerts_box = QGroupBox("Alertas prioritarias")
    alerts_box.setObjectName("infoCard")
    alerts_layout = QVBoxLayout()
    alerts_layout.setSpacing(6)
    alerts_intro = QLabel("Seguimiento rapido de apartados y pendientes.")
    alerts_intro.setObjectName("inventorySubtitle")
    window.layaway_alerts_label.setObjectName("analyticsFlagCard")
    alerts_layout.addWidget(alerts_intro)
    alerts_layout.addWidget(window.layaway_alerts_label)
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
    manual_promo_box.setLayout(manual_promo_layout)
    window.dashboard_manual_promo_box = manual_promo_box

    info_grid = QGridLayout()
    info_grid.setHorizontalSpacing(10)
    info_grid.setVerticalSpacing(10)
    info_grid.addWidget(business_box, 0, 0)
    info_grid.addWidget(alerts_box, 0, 1)
    info_grid.addWidget(manual_promo_box, 1, 0, 1, 2)
    info_grid.setColumnStretch(0, 1)
    info_grid.setColumnStretch(1, 1)

    layout.addLayout(kpi_grid)
    layout.addLayout(info_grid)
    layout.addStretch()
    widget.setLayout(layout)
    return widget
