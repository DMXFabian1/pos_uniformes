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
                background: #faeadf;
                color: #7e3a22;
                border: 1px solid #efccb8;
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
                background: #fbf3ec;
                color: #8c6656;
                border: 1px solid #ecd5c5;
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
                background: #fbf3ec;
                color: #8c6656;
                border: 1px solid #ecd5c5;
            }
            #cashierTotalsCard {
                background: #a84f2d;
                border: 1px solid #8a4326;
                border-radius: 16px;
            }
            #cashierTotalValue {
                background: transparent;
                color: #f9f4ea;
                border: none;
                padding: 0;
                font-size: 30px;
                font-weight: 900;
            }
            #cashierMetaLabel {
                background: transparent;
                color: #f1d7c5;
                border: none;
                padding: 0;
                font-size: 12px;
                font-weight: 700;
            }
            #cashierChangeValue {
                background: #faeadf;
                color: #7e3a22;
                border: 1px solid #efccb8;
                border-radius: 12px;
                padding: 7px 10px;
                font-size: 13px;
                font-weight: 800;
            }
            """
