"""Secciones inventory y analytics del stylesheet principal."""

from __future__ import annotations


def build_main_window_inventory_analytics_styles() -> str:
    return """
            #inventoryTitle {
                color: #7e3a22;
                font-size: 20px;
                font-weight: 800;
                background: transparent;
                border: none;
                padding: 0;
            }
            #inventorySubtitle {
                color: #6f665f;
                font-size: 13px;
                font-weight: 600;
                background: transparent;
                border: none;
                padding: 0;
            }
            #inventoryStatusBadge {
                background: #f6decd;
                color: #7e3a22;
                border: 1px solid #e1b89d;
                border-radius: 999px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 800;
            }
            #inventoryStatusBadge[tone="positive"] {
                background: #f8dfcf;
                color: #8f4527;
                border: 1px solid #dfb496;
            }
            #inventoryStatusBadge[tone="warning"] {
                background: #fbf0cf;
                color: #8a5a00;
                border: 1px solid #e7d49b;
            }
            #inventoryStatusBadge[tone="danger"] {
                background: #f8dfd9;
                color: #9a2f22;
                border: 1px solid #dfb3aa;
            }
            #inventoryStatusBadge[tone="muted"], #inventoryStatusBadge[tone="neutral"] {
                background: #ece8e1;
                color: #6e675f;
                border: 1px solid #d7cec1;
            }
            #inventoryMetaCard, #inventoryMetaCardAlt {
                border-radius: 14px;
                padding: 10px 12px;
                border: 1px solid #e4dacd;
                font-weight: 600;
            }
            #inventoryMetaCard {
                background: #faeadf;
                color: #8a4326;
                border: 1px solid #efccb8;
            }
            #inventoryMetaCardAlt {
                background: #fbf3ec;
                color: #8c6656;
                border: 1px solid #ecd5c5;
            }
            #inventoryQrCaption {
                color: #6f665f;
                font-size: 12px;
                background: transparent;
                border: none;
                padding: 0 4px 2px 4px;
            }
            #inventoryCounterChip {
                background: #fae9dc;
                color: #92492a;
                border: 1px solid #ecc7ac;
                border-radius: 999px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #inventoryCounterChip[tone="positive"], #inventoryQrStatus[tone="positive"] {
                background: #f8dfcf;
                color: #8f4527;
                border: 1px solid #dfb496;
            }
            #inventoryCounterChip[tone="warning"], #inventoryQrStatus[tone="warning"] {
                background: #fbf0cf;
                color: #8a5a00;
                border: 1px solid #e7d49b;
            }
            #inventoryCounterChip[tone="danger"], #inventoryQrStatus[tone="danger"] {
                background: #f8dfd9;
                color: #9a2f22;
                border: 1px solid #dfb3aa;
            }
            #inventoryCounterChip[tone="muted"], #inventoryCounterChip[tone="neutral"],
            #inventoryQrStatus[tone="muted"], #inventoryQrStatus[tone="neutral"] {
                background: #ece8e1;
                color: #6e675f;
                border: 1px solid #d7cec1;
            }
            #inventoryQrStatus {
                border-radius: 12px;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #analyticsFlagCard {
                border-radius: 14px;
                padding: 10px 12px;
                border: 1px solid #ecd5c5;
                background: #fbf3ec;
                color: #8c6656;
                font-size: 13px;
                font-weight: 800;
            }
            #analyticsFlagCard[tone="positive"] {
                background: #f8dfcf;
                color: #8f4527;
                border: 1px solid #dfb496;
            }
            #analyticsFlagCard[tone="warning"] {
                background: #fbf0cf;
                color: #8a5a00;
                border: 1px solid #e7d49b;
            }
            #analyticsFlagCard[tone="danger"] {
                background: #f8dfd9;
                color: #9a2f22;
                border: 1px solid #dfb3aa;
            }
            #analyticsFlagCard[tone="neutral"], #analyticsFlagCard[tone="muted"] {
                background: #fbf3ec;
                color: #8c6656;
                border: 1px solid #ecd5c5;
            }
            """
