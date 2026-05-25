"""Secciones hero y cashier del stylesheet principal."""

from __future__ import annotations


def build_main_window_hero_cashier_styles() -> str:
    return """
            #heroPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6f331d, stop:0.55 #a84f2d, stop:1 #c96a35);
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
            #heroTitle {
                color: #f9f4ea;
                font-size: 22px;
                font-weight: 800;
            }
            #heroSubtitle {
                color: #f4d5bf;
                font-size: 12px;
            }
            #heroInfoCard {
                background: rgba(249, 244, 234, 0.09);
                border: 1px solid rgba(249, 244, 234, 0.14);
                border-radius: 14px;
            }
            #heroPrimaryText {
                color: #f9f4ea;
                font-size: 16px;
                font-weight: 800;
                background: transparent;
                border: none;
                padding: 0;
            }
            #heroMetaText {
                color: #f6ddca;
                font-size: 11px;
                font-weight: 700;
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 999px;
                padding: 5px 9px;
            }
            #cashierSummaryCard {
                background: #f5ede5;
                color: #4a3020;
                border: 1px solid #d8c9b8;
                border-radius: 14px;
                padding: 10px 12px;
                font-size: 15px;
                font-weight: 800;
            }
            #cashierWarningLine {
                background: #fbf0cf;
                color: #8a5a00;
                border: 1px solid #e7d49b;
                border-radius: 12px;
                padding: 7px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #cashierFeedbackLabel {
                background: #f5f0ea;
                color: #5a4a3f;
                border: 1px solid #d8cfc3;
                border-radius: 12px;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #cashierFeedbackLabel[tone="positive"] {
                background: #f8dfcf;
                color: #8f4527;
                border: 1px solid #dfb496;
            }
            #cashierFeedbackLabel[tone="warning"] {
                background: #fbf0cf;
                color: #8a5a00;
                border: 1px solid #e7d49b;
            }
            #cashierFeedbackLabel[tone="danger"] {
                background: #f8dfd9;
                color: #9a2f22;
                border: 1px solid #dfb3aa;
            }
            #cashierFeedbackLabel[tone="neutral"] {
                background: #f5f0ea;
                color: #5a4a3f;
                border: 1px solid #d8cfc3;
            }
            #cashierTotalsCard {
                background: #2c1810;
                border: 1px solid #1a0e08;
                border-radius: 16px;
            }
            #cashierCartTable {
                background: #fdfcf9;
                alternate-background-color: #f5f0e9;
                gridline-color: #e4dbd1;
                border: 1px solid #d8cfc3;
                border-radius: 18px;
                selection-background-color: #fdeae2;
                selection-color: #4a2810;
                font-size: 14px;
                font-weight: 700;
            }
            #cashierCartTable::item {
                padding: 8px 10px;
            }
            #cashierCartTable QHeaderView::section {
                background: #f0ebe4;
                color: #4a3728;
                border: none;
                border-right: 1px solid #d8cfc3;
                border-bottom: 2px solid #c9b5a5;
                padding: 9px 10px;
                font-size: 12px;
                font-weight: 800;
            }
            #cashierTotalValue {
                background: transparent;
                color: #f4d5bf;
                border: none;
                padding: 0;
                font-size: 30px;
                font-weight: 900;
            }
            #cashierMetaLabel {
                background: transparent;
                color: #e8d5c0;
                border: none;
                padding: 0;
                font-size: 12px;
                font-weight: 700;
            }
            #cashierChangeValue {
                background: #e5f2eb;
                color: #245241;
                border: 1px solid #bfdccd;
                border-radius: 12px;
                padding: 7px 10px;
                font-size: 13px;
                font-weight: 800;
            }
            """
