"""Secciones inventory y analytics del stylesheet principal."""

from __future__ import annotations


def build_main_window_inventory_analytics_styles() -> str:
    return """
            #inventoryTitle {
                color: #3d2b1f;
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
                background: #f0ebe4;
                color: #51402f;
                border: 1px solid #d8c9b8;
                border-radius: 999px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 800;
            }
            #inventoryStatusBadge[tone="positive"] {
                background: #e5f2eb;
                color: #245241;
                border: 1px solid #bfdccd;
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
                border: 1px solid #ddd4c8;
                font-weight: 600;
            }
            #inventoryMetaCard {
                background: #f5ede5;
                color: #4a3020;
                border: 1px solid #d8c9b8;
            }
            #inventoryMetaCardAlt {
                background: #faf6f2;
                color: #5f564d;
                border: 1px solid #ddd4c8;
            }
            #inventoryQrCaption {
                color: #6f665f;
                font-size: 12px;
                background: transparent;
                border: none;
                padding: 0 4px 2px 4px;
            }
            #inventoryCounterChip {
                background: #f0ebe4;
                color: #51402f;
                border: 1px solid #d8c9b8;
                border-radius: 999px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #inventoryCounterChip[tone="positive"], #inventoryQrStatus[tone="positive"] {
                background: #e5f2eb;
                color: #245241;
                border: 1px solid #bfdccd;
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
                background: #f0ebe4;
                color: #51402f;
                border: 1px solid #d8c9b8;
                border-radius: 12px;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            #analyticsFlagCard {
                border-radius: 14px;
                padding: 10px 12px;
                border: 1px solid #ddd0c0;
                background: #fdfaf6;
                color: #7a6d60;
                font-size: 13px;
                font-weight: 800;
            }
            #analyticsFlagCard[tone="positive"] {
                background: #e5f2eb;
                color: #245241;
                border: 1px solid #bfdccd;
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
                background: #fdfaf6;
                color: #7a6d60;
                border: 1px solid #ddd0c0;
            }
            """
