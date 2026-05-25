"""Secciones de controles del stylesheet principal."""

from __future__ import annotations

from pos_uniformes.ui.styles.interactive_hover_styles import (
    build_combo_popup_hover_styles,
    build_menu_popup_hover_styles,
)


def build_main_window_control_styles() -> str:
    combo_popup_styles = build_combo_popup_hover_styles(
        popup_background="#fffdf8",
        popup_color="#1f1f1b",
        popup_border="#d8cfc3",
        selected_background="#f4d4bb",
        selected_color="#73341c",
        hover_background="#e7eef5",
        hover_color="#2d475d",
        selected_hover_background="#d8e4ee",
        selected_hover_color="#20384d",
    )
    menu_popup_styles = build_menu_popup_hover_styles(
        menu_background="#fffdf8",
        menu_color="#2c2a27",
        menu_border="#d8cfc3",
        hover_background="#e7eef5",
        hover_color="#2d475d",
        selected_background="#d8e4ee",
        selected_color="#20384d",
    )
    return "\n".join(
        [
            """
            QPushButton {
                background: #a84f2d;
                color: #f9f4ea;
                border: none;
                border-radius: 12px;
                padding: 10px 16px;
                font-weight: 700;
            }
            QPushButton#adminCompactButton {
                border-radius: 10px;
                padding: 7px 12px;
                min-height: 30px;
            }
            QPushButton#inventoryActionButton {
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 30px;
                font-size: 13px;
                text-align: left;
            }
            QToolButton#inventoryMenuButton, QToolButton#inventoryMenuSecondaryButton {
                border-radius: 10px;
                padding: 6px 12px;
                min-height: 30px;
                font-size: 13px;
                font-weight: 800;
                text-align: left;
            }
            QToolButton#inventoryMenuButton {
                background: #a84f2d;
                color: #f7f1e8;
                border: 1px solid #8a4326;
            }
            QToolButton#inventoryMenuButton:hover {
                background: #bb613c;
            }
            QToolButton#inventoryMenuSecondaryButton {
                background: #efe7d9;
                color: #2c2a27;
                border: 1px solid #d6ccbe;
            }
            QToolButton#inventoryMenuSecondaryButton:hover {
                background: #e6dccd;
            }
            QToolButton#inventoryMenuButton::menu-indicator, QToolButton#inventoryMenuSecondaryButton::menu-indicator {
                subcontrol-origin: padding;
                subcontrol-position: right center;
                right: 8px;
            }
            QPushButton#inventoryDangerButton {
                background: #f4e1dc;
                color: #7e2f1f;
                border: 1px solid #d9b4ab;
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 30px;
                font-size: 13px;
                text-align: left;
            }
            QPushButton#inventoryDangerButton:hover {
                background: #ecd1ca;
            }
            QPushButton#cashierDangerButton {
                background: #f4e1dc;
                color: #7e2f1f;
                border: 1px solid #d9b4ab;
                border-radius: 10px;
                padding: 6px 12px;
                min-height: 30px;
            }
            QPushButton#cashierDangerButton:hover {
                background: #ecd1ca;
            }
            QPushButton#inventorySecondaryButton {
                background: #efe7d9;
                color: #2c2a27;
                border: 1px solid #d6ccbe;
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 30px;
                font-size: 13px;
                text-align: left;
            }
            QPushButton#inventorySecondaryButton:hover {
                background: #e6dccd;
            }
            QPushButton#iconButton {
                border-radius: 10px;
                min-width: 34px;
                max-width: 34px;
                min-height: 34px;
                max-height: 34px;
                padding: 0;
                font-size: 18px;
            }
            QPushButton#toolbarSecondaryButton, QPushButton#toolbarGhostButton, QPushButton#toolbarPrimaryButton,
            QPushButton#toolbarSoftButton, QPushButton#toolbarActionButton, QPushButton#toolbarDangerButton,
            QPushButton#toolbarAccentButton, QToolButton#toolbarSecondaryButton, QToolButton#toolbarGhostButton,
            QToolButton#toolbarSoftButton, QToolButton#toolbarActionButton, QToolButton#toolbarDangerButton,
            QToolButton#toolbarAccentButton {
                border-radius: 10px;
                padding: 6px 12px;
                min-height: 34px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #bb613c;
            }
            QPushButton:pressed {
                background: #6f331d;
            }
            QPushButton:disabled {
                background: #c8c0b6;
                color: #f7f1e8;
            }
            QPushButton#primaryButton {
                background: #a84f2d;
            }
            QPushButton#primaryButton:hover {
                background: #bb613c;
            }
            QPushButton#ghostButton, QPushButton#secondaryButton, QPushButton#toolbarSecondaryButton, QPushButton#toolbarGhostButton,
            QToolButton#toolbarSecondaryButton, QToolButton#toolbarGhostButton {
                background: #efe7d9;
                color: #2c2a27;
                border: 1px solid #d6ccbe;
            }
            QPushButton#ghostButton:hover, QPushButton#secondaryButton:hover, QPushButton#toolbarSecondaryButton:hover, QPushButton#toolbarGhostButton:hover,
            QToolButton#toolbarSecondaryButton:hover, QToolButton#toolbarGhostButton:hover {
                background: #e6dccd;
            }
            QPushButton#toolbarPrimaryButton, QToolButton#toolbarPrimaryButton {
                background: #a84f2d;
            }
            QPushButton#toolbarPrimaryButton:hover, QToolButton#toolbarPrimaryButton:hover {
                background: #bb613c;
            }
            QPushButton#toolbarSoftButton, QToolButton#toolbarSoftButton {
                background: #fae9dc;
                color: #a84f2d;
                border: 1px solid #ecc7ac;
            }
            QPushButton#toolbarSoftButton:hover, QToolButton#toolbarSoftButton:hover {
                background: #f8dfcf;
            }
            QPushButton#toolbarActionButton, QToolButton#toolbarActionButton {
                background: #a84f2d;
                color: #f7f1e8;
                border: 1px solid #8a4326;
            }
            QPushButton#toolbarActionButton:hover, QToolButton#toolbarActionButton:hover {
                background: #bb613c;
            }
            QPushButton#toolbarDangerButton, QToolButton#toolbarDangerButton {
                background: #f4e1dc;
                color: #7e2f1f;
                border: 1px solid #d9b4ab;
            }
            QPushButton#toolbarDangerButton:hover, QToolButton#toolbarDangerButton:hover {
                background: #ecd1ca;
            }
            QPushButton#toolbarAccentButton, QToolButton#toolbarAccentButton {
                background: #a84f2d;
                color: #f9f4ea;
                border: 1px solid #944226;
            }
            QPushButton#toolbarAccentButton:hover, QToolButton#toolbarAccentButton:hover {
                background: #bb613c;
            }
            QToolButton#toolbarSoftButton::menu-indicator, QToolButton#toolbarActionButton::menu-indicator,
            QToolButton#toolbarSecondaryButton::menu-indicator, QToolButton#toolbarGhostButton::menu-indicator {
                subcontrol-origin: padding;
                subcontrol-position: right center;
                right: 8px;
            }
            QLineEdit, QComboBox, QSpinBox, QTextEdit {
                background: #fffdf8;
                border: 1px solid #d8cfc3;
                border-radius: 12px;
                padding: 8px 12px;
                min-height: 34px;
                selection-background-color: #a84f2d;
            }
            QLineEdit#inventoryFilterInput, QComboBox#inventoryFilterCombo {
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 30px;
            }
            QLabel#inventoryFilterLabel {
                color: #5f564d;
                font-size: 12px;
                font-weight: 700;
                background: transparent;
                border: none;
                padding: 0 2px;
            }
            QComboBox#inventoryFilterCombo:hover, QLineEdit#inventoryFilterInput:hover {
                background: #f9efe7;
                border: 1px solid #dfb496;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
                border: 2px solid #c96a35;
            }
            QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {
                border: none;
                width: 22px;
            }
            """,
            combo_popup_styles,
            menu_popup_styles,
            """
            QToolButton#secondaryButton {
                background: #efe7d9;
                color: #2c2a27;
                border: 1px solid #d6ccbe;
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 30px;
                font-size: 13px;
                font-weight: 700;
                text-align: left;
            }
            QToolButton#secondaryButton:hover {
                background: #e6dccd;
            }
            """,
            """
            #dataTable {
                background: #fdfcf9;
                alternate-background-color: #f5f0e9;
                gridline-color: #e4dbd1;
                border: 1px solid #d8cfc3;
                border-radius: 16px;
                selection-background-color: #fdeae2;
                selection-color: #4a2810;
                font-size: 13px;
            }
            QHeaderView::section {
                background: #f0ebe4;
                color: #4a3728;
                border: none;
                border-right: 1px solid #d8cfc3;
                border-bottom: 2px solid #c9b5a5;
                padding: 8px 10px;
                font-weight: 700;
            }
            #qrPreview {
                border: 1.5px dashed #c9b5a5;
                border-radius: 18px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #fdfcf9, stop:1 #f5ede5);
                color: #8a7a6a;
                max-width: 180px;
                max-height: 180px;
                padding: 10px;
            }
            """,
        ]
    )
