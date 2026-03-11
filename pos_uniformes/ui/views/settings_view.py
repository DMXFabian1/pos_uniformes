"""Vista principal del modulo Configuracion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QFrame, QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget
from PyQt6.QtWidgets import QStyle

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def build_settings_tab(window: "MainWindow") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(10)

    actions_box = QGroupBox("Modulos")
    actions_box.setObjectName("infoCard")
    actions_layout = QGridLayout()
    actions_layout.setHorizontalSpacing(10)
    actions_layout.setVerticalSpacing(10)

    settings_buttons = [
        (
            window.settings_users_button,
            "Administra usuarios, roles y acceso al sistema.",
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            window._open_users_settings_dialog,
        ),
        (
            window.settings_suppliers_button,
            "Crea, edita y activa proveedores disponibles para compras.",
            QStyle.StandardPixmap.SP_DirIcon,
            window._open_suppliers_settings_dialog,
        ),
        (
            window.settings_clients_button,
            "Crea y organiza clientes para ventas, apartados y fidelizacion futura.",
            QStyle.StandardPixmap.SP_FileDialogListView,
            window._open_clients_settings_dialog,
        ),
        (
            window.settings_whatsapp_button,
            "Configura plantillas de mensajes para clientes y apartados.",
            QStyle.StandardPixmap.SP_MessageBoxInformation,
            window._open_whatsapp_settings_dialog,
        ),
        (
            window.settings_backup_button,
            "Crea respaldos, revisa el historial y restaura respaldos .dump.",
            QStyle.StandardPixmap.SP_DriveFDIcon,
            window._open_backup_settings_dialog,
        ),
        (
            window.settings_cash_history_button,
            "Revisa aperturas, cierres, responsables y diferencias de caja.",
            QStyle.StandardPixmap.SP_FileDialogContentsView,
            window._open_cash_history_settings_dialog,
        ),
        (
            window.settings_business_button,
            "Configura datos del negocio, ticket e impresion.",
            QStyle.StandardPixmap.SP_FileDialogInfoView,
            window._open_business_settings_dialog,
        ),
    ]
    for index, (button, description, icon_name, handler) in enumerate(settings_buttons):
        row, column = divmod(index, 3)
        button.setObjectName("settingsLaunchButton")
        button.setIcon(window.style().standardIcon(icon_name))
        button.setIconSize(QSize(18, 18))
        button.setMinimumHeight(50)
        button.clicked.connect(handler)
        card = QFrame()
        card.setObjectName("settingsLaunchCard")
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(6)
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setObjectName("subtleLine")
        card_layout.addWidget(button)
        card_layout.addWidget(description_label)
        card.setLayout(card_layout)
        actions_layout.addWidget(card, row, column)
    for column in range(3):
        actions_layout.setColumnStretch(column, 1)
    actions_box.setLayout(actions_layout)

    layout.addWidget(actions_box)
    layout.addStretch()
    widget.setLayout(layout)
    return widget
