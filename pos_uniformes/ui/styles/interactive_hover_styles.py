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


def build_menu_popup_hover_styles(
    *,
    menu_background: str,
    menu_color: str,
    menu_border: str,
    hover_background: str,
    hover_color: str,
    selected_background: str,
    selected_color: str,
) -> str:
    return f"""
            QMenu {{
                background: {menu_background};
                color: {menu_color};
                border: 1px solid {menu_border};
                border-radius: 12px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 12px;
                margin: 2px 0;
                border-radius: 8px;
                background: transparent;
            }}
            QMenu::item:selected {{
                background: {hover_background};
                color: {hover_color};
            }}
            QMenu::item:checked {{
                background: {selected_background};
                color: {selected_color};
            }}
            QMenu::item:selected:disabled {{
                background: transparent;
                color: {menu_color};
            }}
            QMenu::item:disabled {{
                color: #8f8a82;
            }}
            QMenu::separator {{
                height: 1px;
                background: {menu_border};
                margin: 6px 8px;
            }}
            """


def build_button_hover_styles(
    *,
    selector: str,
    hover_background: str,
    hover_color: str,
    hover_border: str | None = None,
) -> str:
    border_line = f"border: 1px solid {hover_border};" if hover_border is not None else ""
    return f"""
            {selector}:hover {{
                background: {hover_background};
                color: {hover_color};
                {border_line}
            }}
            """
