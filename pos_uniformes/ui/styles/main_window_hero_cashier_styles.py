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
                background: #edf3f7;
                color: #29485d;
                border: 1px solid #d6e2ea;
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
                background: #f1f5f8;
                color: #5a6774;
                border: 1px solid #d6e2ea;
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
                background: #f1f5f8;
                color: #5a6774;
                border: 1px solid #d6e2ea;
            }
            #cashierTotalsCard {
                background: #324252;
                border: 1px solid #263443;
                border-radius: 16px;
            }
            #cashierCartTable {
                background: #fcfbf8;
                alternate-background-color: #eef3f7;
                gridline-color: #d8e0e7;
                border: 1px solid #d8e0e7;
                border-radius: 18px;
                selection-background-color: #d5e3ef;
                selection-color: #233c51;
                font-size: 14px;
                font-weight: 700;
            }
            #cashierCartTable::item {
                padding: 8px 10px;
            }
            #cashierCartTable QHeaderView::section {
                background: #dde7ef;
                color: #3f4e5a;
                border: none;
                border-right: 1px solid #d0dbe4;
                border-bottom: 1px solid #d0dbe4;
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
                color: #d8e3ec;
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
