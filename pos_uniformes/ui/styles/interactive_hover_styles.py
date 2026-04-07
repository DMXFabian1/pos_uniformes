"""Helpers reutilizables para hover de controles interactivos."""

from __future__ import annotations


def build_combo_popup_hover_styles(
    *,
    popup_background: str,
    popup_color: str,
    popup_border: str,
    selected_background: str,
    selected_color: str,
    hover_background: str,
    hover_color: str,
    selected_hover_background: str,
    selected_hover_color: str,
) -> str:
    return f"""
            QComboBox QAbstractItemView {{
                background: {popup_background};
                color: {popup_color};
                border: 1px solid {popup_border};
                selection-background-color: {selected_background};
                selection-color: {selected_color};
                outline: 0;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 30px;
                padding: 6px 10px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: {hover_background};
                color: {hover_color};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: {selected_background};
                color: {selected_color};
                font-weight: 700;
            }}
            QComboBox QAbstractItemView::item:selected:hover {{
                background: {selected_hover_background};
                color: {selected_hover_color};
            }}
            """
