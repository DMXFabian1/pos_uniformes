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
                border: 1px solid #ddd4c8;
                border-radius: 18px;
                background: #faf9f5;
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
                background: #f0ebe4;
                color: #4a3728;
            }
            #statusLine, #subtleLine, #analyticsLine {
                background: #f5f0ea;
                border: 1px solid #d8cfc3;
                border-radius: 12px;
                padding: 6px 10px;
            }
            #catalogSpotlightCard, #catalogFiltersCard, #catalogStatusStrip {
                background: #fdfcf9;
                border: 1px solid #ddd4c8;
                border-radius: 16px;
                padding: 10px 12px;
            }
            #catalogSpotlightCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #fdfcf9,
                    stop: 1 #f5ede5
                );
                border: 1px solid #ddd4c8;
            }
            #catalogStatusStrip {
                background: #faf6f2;
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
                background: rgba(245, 240, 234, 0.9);
                border: 1px solid #ddd4c8;
                border-radius: 14px;
                padding: 6px 10px;
                color: #4a3728;
                font-weight: 700;
            }
            #catalogSummaryLine {
                background: #f0ebe4;
                border: 1px solid #c9b5a5;
                border-radius: 14px;
                padding: 6px 10px;
                color: #4a3020;
                font-weight: 800;
            }
            #catalogPagerLine, #catalogSupportLine {
                background: #f5f0ea;
                border: 1px solid #d8cfc3;
                border-radius: 12px;
                padding: 5px 9px;
            }
            #catalogPagerLine {
                color: #5f504a;
                font-weight: 700;
            }
            #catalogSupportLine {
                color: #6a5a50;
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
                background: #f0ebe4;
                color: #514030;
                border: 1px solid #d8c9b8;
                border-radius: 999px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #chipButton:hover {
                background: #e8dfd8;
                border-color: #c9b5a5;
                color: #4a3020;
            }
            #chipButton[active="true"] {
                background: #a84f2d;
                color: #f9f4ea;
                border-color: #8a4326;
            }
            #stepButton {
                background: #f0ebe4;
                color: #514030;
                border: 1px solid #d8c9b8;
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
                background: #e8dfd8;
                color: #4a3020;
                border-color: #c9b5a5;
            }
            #analyticsLine {
                background: #f0ebe4;
                color: #514030;
            }
            #readOnlyField {
                background: #f5f0ea;
                color: #5a4a3f;
                border: 1px solid #d8cfc3;
                border-radius: 12px;
                padding: 9px 12px;
                font-weight: 700;
            }
            #quoteFormLabel {
                background: transparent;
                border: none;
                color: #7a4f39;
                padding: 0;
                font-size: 12px;
                font-weight: 800;
            }
            #quoteDetailCard {
                background: #fdfcf9;
                border: 1px solid #ddd4c8;
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
                background: #f8fafb;
                border: 1px solid #dce5eb;
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
                background: #fdfcf9;
                border: 1px solid #ddd4c8;
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
                background: #f8fafb;
                border: 1px solid #dce5eb;
                border-radius: 20px;
            }
            #kpiCard[tone="positive"] {
                background: #eef8f2;
                border: 1px solid #c9dfd2;
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
                background: #f8fafb;
                border: 1px solid #dce5eb;
            }
            #kpiTitle {
                color: #66707a;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                font-weight: 700;
            }
            #kpiValue {
                color: #355167;
                font-size: 30px;
                font-weight: 800;
            }
            #kpiSubtitle {
                color: #78818a;
                font-size: 12px;
            }
            #kpiSubtitle[tone="positive"] {
                color: #245241;
            }
            #kpiSubtitle[tone="warning"] {
                color: #8a5a00;
            }
            #kpiSubtitle[tone="danger"] {
                color: #9a2f22;
            }
            """
