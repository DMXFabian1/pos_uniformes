"""Estilos visuales de la ventana satélite de presupuestos."""

from __future__ import annotations

from pos_uniformes.ui.styles.interactive_hover_styles import (
    build_button_hover_styles,
    build_combo_popup_hover_styles,
)


def build_satellite_stylesheet() -> str:
    combo_popup = build_combo_popup_hover_styles(
        popup_background="#fffdf8",
        popup_color="#1f1f1b",
        popup_border="#d8cfc3",
        selected_background="#f4d4bb",
        selected_color="#73341c",
        hover_background="#a9c1d6",
        hover_color="#0f2940",
        selected_hover_background="#98b4cd",
        selected_hover_color="#0b2237",
    )
    button_hover = "\n".join((
        build_button_hover_styles(
            selector="QPushButton#primaryButton",
            hover_background="#bb613c",
            hover_color="#f9f4ea",
        ),
        build_button_hover_styles(
            selector="QPushButton#secondaryButton",
            hover_background="#e6dccd",
            hover_color="#2c2a27",
            hover_border="#d6ccbe",
        ),
        build_button_hover_styles(
            selector="QPushButton#ghostButton",
            hover_background="#e6dccd",
            hover_color="#2c2a27",
            hover_border="#d6ccbe",
        ),
        build_button_hover_styles(
            selector="QPushButton#dangerButton",
            hover_background="#ecd1ca",
            hover_color="#7e2f1f",
            hover_border="#d9b4ab",
        ),
        build_button_hover_styles(
            selector="QPushButton#navButton",
            hover_background="#e6dccd",
            hover_color="#2c2a27",
            hover_border="#d6ccbe",
        ),
        build_button_hover_styles(
            selector="QPushButton#guidedChoiceButton",
            hover_background="#e6dccd",
            hover_color="#2c2a27",
            hover_border="#d6ccbe",
        ),
        build_button_hover_styles(
            selector="QPushButton#guidedProductButton",
            hover_background="#e6dccd",
            hover_color="#2c2a27",
            hover_border="#d6ccbe",
        ),
        build_button_hover_styles(
            selector="QPushButton#sidebarItemRemoveButton",
            hover_background="#ead8c9",
            hover_color="#73341c",
            hover_border="#d3bca8",
        ),
        build_button_hover_styles(
            selector="QPushButton#addToCartButton",
            hover_background="#c96a35",
            hover_color="#fff8f0",
        ),
    ))

    return "\n".join([
        _BASE_STYLES,
        combo_popup,
        _COMPONENT_STYLES,
        button_hover,
    ])


_BASE_STYLES = """
QMainWindow {
    background: #f3efe8;
    color: #1f1c19;
    font-family: "Avenir Next", "Helvetica Neue", sans-serif;
    font-size: 14px;
}
QPushButton#exitButton {
    background: transparent;
    color: rgba(255, 255, 255, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
}
QPushButton#exitButton:hover {
    background: rgba(255, 255, 255, 0.12);
    color: rgba(255, 255, 255, 0.85);
    border-color: rgba(255, 255, 255, 0.45);
}
QLabel#offlineBanner {
    background: #f5c842;
    color: #3d2600;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 14px;
    border-radius: 8px;
}
QGroupBox {
    border: 1px solid #dce5eb;
    border-radius: 16px;
    margin-top: 10px;
    padding-top: 6px;
    background: #fbf8f2;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #87492c;
}
QFrame#guidedStepsCard {
    border: 1px solid #ddd0c0;
    border-radius: 20px;
    background: #fdfaf6;
}
QFrame#satHeaderCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6f331d, stop:0.55 #a84f2d, stop:1 #c96a35);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 18px;
}
QFrame#satTotalsCard {
    background: #fbf8f2;
    border: 1px solid #dce5eb;
    border-radius: 18px;
}
QFrame#satSidebarCard {
    background: #fbf8f2;
    border: 1px solid #dce5eb;
    border-radius: 22px;
}
QFrame#satSidebarItemCard {
    background: #f8f2e9;
    border: 1px solid #e3d8ca;
    border-radius: 16px;
}
QLabel#satTitle {
    font-size: 20px;
    font-weight: 800;
    color: #f9f4ea;
}
QLabel#satMeta {
    color: #f6ddca;
    font-size: 12px;
}
QLabel#satFieldLabel {
    color: #7a6d60;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.4px;
    text-transform: uppercase;
}
QLabel#satPager {
    background: #f5f8fa;
    border: 1px solid #dce5eb;
    border-radius: 12px;
    padding: 5px 9px;
    color: #5f6870;
    font-size: 13px;
    font-weight: 800;
}
QLabel#quoteActionHint {
    color: #7a6f64;
    font-size: 12px;
    padding: 2px 0px;
}
QLabel#satStatus {
    background: rgba(249, 244, 234, 0.09);
    border: 1px solid rgba(249, 244, 234, 0.14);
    border-radius: 14px;
    padding: 8px 12px;
    color: #f9f4ea;
    font-weight: 700;
}
QLabel#satTotal {
    font-size: 28px;
    font-weight: 900;
    color: #87492c;
}
QLabel#satSummary {
    color: #304d60;
    background: #f2ece3;
    border: 1px solid #d8e2ea;
    border-radius: 12px;
    padding: 10px 12px;
}
QLabel#satSidebarTitle {
    font-size: 15px;
    font-weight: 900;
    color: #87492c;
}
QLabel#satSidebarTotal {
    font-size: 28px;
    font-weight: 900;
    color: #87492c;
}
QLabel#satSidebarSummary {
    color: #66717b;
    background: #f1ebe2;
    border: 1px solid #dce5eb;
    border-radius: 12px;
    padding: 10px 12px;
}
QLabel#satSidebarSectionMeta {
    color: #7a6d60;
    font-size: 12px;
    font-weight: 700;
}
QLabel#satSidebarItemQty {
    background: #e6dccd;
    color: #654e3d;
    border-radius: 10px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 900;
}
QLabel#satSidebarItemName {
    color: #2f2a24;
    font-size: 13px;
    font-weight: 800;
}
QLabel#satSidebarItemMeta {
    color: #6f665d;
    font-size: 12px;
}
QLabel#satSidebarItemEmpty {
    color: #6f665d;
    background: #f3ece3;
    border: 1px dashed #dacdbf;
    border-radius: 14px;
    padding: 12px;
}
QScrollArea#satSidebarItemsScroll,
QWidget#satSidebarItemsViewport,
QWidget#satSidebarItemsContent {
    background: transparent;
    border: none;
}
/* ── Kiosko ─────────────────────────────────────────────────── */
QFrame#satScanCard {
    background: #fffdf8;
    border: 1px solid #d5c9b9;
    border-radius: 18px;
}
QLabel#satKioskScanLabel {
    color: #9a8478;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
}
QFrame#satProductHeroCard {
    background: #fdfaf4;
    border-top: 4px solid #a84f2d;
    border-left: 1px solid #dfcbb5;
    border-right: 1px solid #dfcbb5;
    border-bottom: 1px solid #dfcbb5;
    border-radius: 20px;
}
QFrame#satHeroDivider {
    background: #e8ddd0;
    border: none;
    max-height: 1px;
    min-height: 1px;
}
QFrame#satRecentCard {
    background: #fbf8f2;
    border: 1px solid #dce5eb;
    border-radius: 18px;
}
QPushButton#addToCartButton {
    background: #a84f2d;
    color: #f9f4ea;
    font-size: 13px;
    font-weight: 900;
    padding: 8px 16px;
    border-radius: 12px;
    min-height: 36px;
}
QPushButton#addToCartButton:disabled {
    background: #d8c9b8;
    color: #9e8e7e;
}
QLabel#satKioskSku {
    font-size: 12px;
    font-weight: 700;
    color: #9a8478;
    letter-spacing: 0.5px;
}
QLabel#satKioskProduct {
    font-size: 30px;
    font-weight: 900;
    color: #2f2a24;
}
QLabel#satKioskTalla {
    font-size: 18px;
    font-weight: 600;
    color: #7a6f64;
}
QLabel#satKioskPrice {
    font-size: 64px;
    font-weight: 900;
    color: #a84f2d;
}
QLabel#satKioskBadge {
    color: #2f2a24;
    background: #e8dfd3;
    border-radius: 12px;
    padding: 8px 14px;
    font-weight: 800;
    font-size: 13px;
}
QLabel#satKioskBody {
    color: #5e574f;
    background: rgba(255, 255, 255, 0.55);
    border: 1px solid #ddd0be;
    border-radius: 10px;
    padding: 9px 12px;
    font-size: 13px;
}
QLabel#satDetailTitle {
    font-size: 16px;
    font-weight: 800;
    color: #2f2a24;
}
QLabel#satFieldValue {
    color: #5e574f;
    font-size: 15px;
    font-weight: 700;
    padding: 6px 0;
}
QLabel#satDetailMeta {
    color: #66717b;
    background: #f1ebe2;
    border: 1px solid #dce5eb;
    border-radius: 12px;
    padding: 10px 12px;
}
QLabel#satDetailNotes {
    color: #5e574f;
    background: #efe5d8;
    border-radius: 12px;
    padding: 10px 12px;
}
QLabel#guidedStepTitle {
    font-size: 14px;
    font-weight: 900;
    color: #3d5c7a;
    background: #eaf2f8;
    border-radius: 10px;
    padding: 7px 14px;
    margin-top: 6px;
}
QLabel#guidedStepTitle[step="1"] { color: #1a5c80; background: #ddf0fa; }
QLabel#guidedStepTitle[step="2"] { color: #27703f; background: #daf2e5; }
QLabel#guidedStepTitle[step="3"] { color: #5a4010; background: #f5edda; }
QLabel#guidedStepTitle[step="4"] { color: #4e1a78; background: #ecddf8; }
QLabel#guidedStepTitle[step="5"] { color: #1a6060; background: #d5f0f0; }
QLabel#guidedStepTitle[step="6"] { color: #701a48; background: #f8d8ec; }
QLabel#guidedStepTitle[step="7"] { color: #216821; background: #d8f0d8; }
QLabel#guidedStepHint {
    color: #7a6d60;
    font-size: 13px;
    padding: 2px 4px;
    margin: 0px;
}
QLabel#guidedGroupLabel {
    color: #5c5048;
    font-size: 12px;
    font-weight: 900;
    padding: 0px;
    margin: 0px;
}
QLabel#guidedPath {
    color: #87492c;
    background: #f0e5d8;
    border: 1px solid #ddd0c0;
    border-radius: 999px;
    padding: 4px 14px;
    font-weight: 700;
    font-size: 12px;
}
QLabel#guidedGroupBoxTitle {
    color: #87492c;
    font-weight: 900;
    font-size: 15px;
    padding: 0px;
    margin: 0px;
}
"""

_COMPONENT_STYLES = """
QLineEdit#satScanInput {
    font-size: 15px;
    font-weight: 700;
    padding: 8px 10px;
    min-height: 0px;
}
QPushButton {
    border-radius: 12px;
    padding: 9px 14px;
    font-weight: 800;
}
QPushButton#chipButton {
    background: #eef3f7;
    color: #465866;
    border: 1px solid #d7e1e8;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton#chipButton:hover {
    background: #dfeaf2;
    border-color: #c5d7e4;
    color: #314c60;
}
QPushButton#chipButton[active="true"] {
    background: #a84f2d;
    color: #f9f4ea;
    border-color: #8a4326;
}
QPushButton#primaryButton {
    background: #87492c;
    color: #f9f4ea;
}
QPushButton#secondaryButton {
    background: #efe4d5;
    color: #2f2a24;
}
QPushButton#ghostButton {
    background: #f8f1e7;
    color: #6d6155;
}
QPushButton#dangerButton {
    background: #b65246;
    color: #fbf8f2;
}
QPushButton#navButton {
    background: #f8f1e7;
    color: #6d6155;
    text-align: left;
    padding: 14px 16px;
    font-size: 15px;
}
QPushButton#sidebarItemRemoveButton {
    background: #efe4d5;
    color: #6c4d3a;
    border: 1px solid #dbcbb8;
    border-radius: 10px;
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 800;
}
QPushButton#navButton:checked {
    background: #87492c;
    color: #f9f4ea;
}
QPushButton#guidedChoiceButton,
QPushButton#guidedProductButton {
    background: #fffaf5;
    color: #2f2a24;
    border: 1.5px solid #ddd0c0;
    text-align: left;
    padding: 12px 16px;
    font-size: 14px;
}
QPushButton#guidedChoiceButton[compactChoice="true"] {
    padding: 8px 12px;
    font-size: 13px;
}
QPushButton#guidedProductButton[compactCard="true"] {
    padding: 8px 12px;
    font-size: 13px;
}
QPushButton#guidedChoiceButton:checked,
QPushButton#guidedProductButton:checked {
    background: #7b2d14;
    color: #fbf8f2;
    border: 1.5px solid #7b2d14;
}
QPushButton#favoriteButton {
    background: transparent;
    color: #c0a090;
    border: none;
    border-radius: 8px;
    padding: 2px 4px;
    font-size: 16px;
    font-weight: 400;
}
QPushButton#favoriteButton:checked {
    color: #c0392b;
}
QPushButton#favoriteButton:hover {
    background: #f5e8e0;
    color: #a84f2d;
}
QPushButton:disabled {
    background: #e8dfd3;
    color: #a39a90;
}
QLineEdit, QTextEdit, QDateEdit, QComboBox, QSpinBox {
    background: #fffaf2;
    border: 1px solid #d5c9b9;
    border-radius: 12px;
    padding: 8px 10px;
    color: #1f1c19;
}
QLineEdit:hover, QTextEdit:hover, QDateEdit:hover, QComboBox:hover, QSpinBox:hover {
    background: #f9efe7;
    border: 1px solid #dfb496;
}
QComboBox#satFilterCombo {
    font-weight: 700;
    color: #2f2a24;
    padding-left: 14px;
}
QComboBox#satFilterCombo:hover {
    background: #e2cfbd;
    color: #1f1b17;
    border: 1px solid #c69367;
}
QLineEdit:focus, QTextEdit:focus, QDateEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 2px solid #c76b39;
}
QComboBox QAbstractItemView {
    border-radius: 10px;
}
QTableWidget {
    background: #fffaf2;
    alternate-background-color: #f5eee5;
    border: 1px solid #dce5eb;
    border-radius: 12px;
    gridline-color: #dce5eb;
    color: #2f2a24;
    selection-background-color: #dfb48f;
    selection-color: #1f1c19;
}
QTableWidget::item {
    color: #2f2a24;
}
QTableWidget::item:selected {
    color: #1f1c19;
}
QHeaderView::section {
    background: #efe4d5;
    color: #304d60;
    border: none;
    border-bottom: 1px solid #d8e2ea;
    padding: 8px;
    font-weight: 800;
}
QHeaderView {
    background: #efe4d5;
}
QTableCornerButton::section {
    background: #efe4d5;
    border: none;
    border-bottom: 1px solid #d8e2ea;
    border-right: 1px solid #d8e2ea;
}
QScrollArea#guidedScrollArea,
QWidget#guidedScrollViewport {
    background: #fdfaf6;
    border: none;
    border-radius: 16px;
}
QWidget#guidedGridSurface {
    background: #fdfaf6;
}
QScrollArea#guidedPageScrollArea,
QWidget#guidedPageViewport,
QWidget#guidedPageSurface,
QWidget#guidedPageRoot {
    background: #f4efe7;
    border: none;
}
QLineEdit#guidedSearchInput {
    font-size: 15px;
    font-weight: 600;
    padding: 10px 16px;
    min-height: 44px;
    border-radius: 14px;
    border: 1.5px solid #d5c9b9;
    background: #fffdf8;
}
QLineEdit#guidedSearchInput:focus {
    border: 2px solid #c76b39;
    background: #fffaf4;
}
"""
