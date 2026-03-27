"""Stylesheet principal de la ventana."""

from __future__ import annotations

from pos_uniformes.ui.styles.main_window_control_styles import (
    build_main_window_control_styles,
)
from pos_uniformes.ui.styles.main_window_hero_cashier_styles import (
    build_main_window_hero_cashier_styles,
)
from pos_uniformes.ui.styles.main_window_inventory_analytics_styles import (
    build_main_window_inventory_analytics_styles,
)


def build_main_window_stylesheet() -> str:
    return "\n".join(
        [
            _build_main_window_shell_styles(),
            build_main_window_hero_cashier_styles(),
            build_main_window_inventory_analytics_styles(),
            build_main_window_control_styles(),
        ]
    )


def _build_main_window_shell_styles() -> str:
    return """
            QMainWindow, QWidget {
                background: #f3efe8;
                color: #1f1f1b;
                font-family: "Avenir Next", "Helvetica Neue", sans-serif;
                font-size: 14px;
            }
            QTabWidget::pane {
                border: 1px solid #d7d0c4;
                border-radius: 18px;
                background: #fbf8f2;
                top: -1px;
                padding: 10px;
            }
            QTabBar::tab {
                background: transparent;
                color: #6d665e;
                padding: 10px 16px;
                margin-right: 6px;
                border-radius: 12px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #a84f2d;
                color: #f7f1e8;
            }
            QTabBar::tab:hover:!selected {
                background: #e7ded0;
                color: #2d2b27;
            }
            #statusLine, #subtleLine, #analyticsLine {
                background: #fffaf2;
                border: 1px solid #e1d8cb;
                border-radius: 12px;
                padding: 6px 10px;
            }
            #catalogSpotlightCard, #catalogFiltersCard, #catalogStatusStrip {
                background: #fffaf4;
                border: 1px solid #e4d7c8;
                border-radius: 16px;
                padding: 10px 12px;
            }
            #catalogSpotlightCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #fff7ef,
                    stop: 1 #f8ecdf
                );
                border: 1px solid #e7cdb8;
            }
            #catalogStatusStrip {
                background: #fffaf2;
            }
            #catalogSectionTitle {
                background: transparent;
                border: none;
                padding: 0;
                color: #5a3224;
                font-size: 14px;
                font-weight: 800;
            }
            #catalogSectionHint {
                background: transparent;
                border: none;
                padding: 0;
                color: #786d62;
                font-size: 11px;
                line-height: 1.35em;
            }
            #catalogSectionCaption {
                background: transparent;
                border: none;
                padding: 0;
                color: #8a4b2f;
                font-size: 11px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }
            #catalogSelectionLine {
                background: rgba(255, 250, 242, 0.72);
                border: 1px solid #ead7c6;
                border-radius: 14px;
                padding: 6px 10px;
                color: #4a4038;
                font-weight: 700;
            }
            #catalogSummaryLine {
                background: #fff7ee;
                border: 1px solid #ebd3c1;
                border-radius: 14px;
                padding: 6px 10px;
                color: #4a352b;
                font-weight: 800;
            }
            #catalogPagerLine, #catalogSupportLine {
                background: #fffaf2;
                border: 1px solid #e6ddcf;
                border-radius: 12px;
                padding: 5px 9px;
            }
            #catalogPagerLine {
                color: #6c6055;
                font-weight: 700;
            }
            #catalogSupportLine {
                color: #6e665e;
            }
            #templatePreviewLabel {
                background: transparent;
                border: none;
                padding: 0;
                color: #4a433d;
                font-size: 12px;
                line-height: 1.35em;
            }
            #liveNameCaption {
                background: transparent;
                border: none;
                padding: 0;
                color: #7e3a22;
                font-size: 11px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }
            #liveNameValue {
                background: transparent;
                border: none;
                padding: 0;
                color: #4a362c;
                font-size: 22px;
                font-weight: 900;
                line-height: 1.15em;
            }
            #liveNameHint {
                background: transparent;
                border: none;
                padding: 0;
                color: #7a7067;
                font-size: 12px;
                font-weight: 600;
            }
            #chipButton {
                background: #efe7d9;
                color: #6b4b3a;
                border: 1px solid #ddcbb8;
                border-radius: 999px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #chipButton:hover {
                background: #f8dfcf;
                border-color: #dfb496;
                color: #8f4527;
            }
            #chipButton[active="true"] {
                background: #a84f2d;
                color: #f9f4ea;
                border-color: #8a4326;
            }
            #stepButton {
                background: #efe7d9;
                color: #6e675f;
                border: 1px solid #ddd3c6;
                border-radius: 999px;
                padding: 7px 12px;
                font-size: 12px;
                font-weight: 800;
            }
            #stepButton[active="true"] {
                background: #a84f2d;
                color: #f7f1e8;
                border-color: #8a4326;
            }
            #stepButton:hover {
                background: #f8dfcf;
                color: #8f4527;
                border-color: #dfb496;
            }
            #analyticsLine {
                background: #efe7d9;
                color: #4a433d;
            }
            #readOnlyField {
                background: #f2eee6;
                color: #564d45;
                border: 1px solid #ddd3c6;
                border-radius: 12px;
                padding: 9px 12px;
                font-weight: 700;
            }
            #quoteDetailCard {
                background: #fff9f1;
                border: 1px solid #eadccc;
                border-radius: 14px;
            }
            #quoteDetailTitle {
                background: transparent;
                border: none;
                color: #3f2c23;
                font-size: 18px;
                font-weight: 900;
                padding: 0;
            }
            #quoteDetailMetaText {
                background: transparent;
                border: none;
                color: #61564d;
                font-size: 12px;
                font-weight: 700;
                line-height: 1.35em;
                padding: 0;
            }
            #quoteDetailNotesText {
                background: transparent;
                border: none;
                color: #6a6057;
                font-size: 12px;
                font-weight: 600;
                line-height: 1.35em;
                padding: 0;
            }
            #settingsLaunchCard {
                background: #fffaf2;
                border: 1px solid #ddd3c6;
                border-radius: 18px;
            }
            QPushButton#settingsLaunchButton {
                background: #a84f2d;
                color: #f9f4ea;
                border: none;
                border-radius: 14px;
                padding: 14px 16px;
                text-align: left;
                font-size: 15px;
                font-weight: 800;
            }
            QPushButton#settingsLaunchButton:hover {
                background: #bb613c;
            }
            QGroupBox, #infoCard {
                background: #fffaf2;
                border: 1px solid #ddd3c6;
                border-radius: 18px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 6px;
                color: #51483f;
            }
            #kpiCard {
                background: #fffaf2;
                border: 1px solid #ddd3c6;
                border-radius: 20px;
            }
            #kpiCard[tone="positive"] {
                background: #fff8f0;
                border: 1px solid #e1c5b2;
            }
            #kpiCard[tone="warning"] {
                background: #fff9ec;
                border: 1px solid #ead7a8;
            }
            #kpiCard[tone="danger"] {
                background: #fff4f1;
                border: 1px solid #e3c0b8;
            }
            #kpiCard[tone="neutral"], #kpiCard[tone="muted"] {
                background: #fffaf2;
                border: 1px solid #ddd3c6;
            }
            #kpiTitle {
                color: #6b625a;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                font-weight: 700;
            }
            #kpiValue {
                color: #7a351d;
                font-size: 30px;
                font-weight: 800;
            }
            #kpiSubtitle {
                color: #857b70;
                font-size: 12px;
            }
            #kpiSubtitle[tone="positive"] {
                color: #8f4527;
            }
            #kpiSubtitle[tone="warning"] {
                color: #8a5a00;
            }
            #kpiSubtitle[tone="danger"] {
                color: #9a2f22;
            }
            """
