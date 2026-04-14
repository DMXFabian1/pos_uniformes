"""Helpers visuales para chips removibles de filtros activos."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PyQt6.QtWidgets import QPushButton, QWidget

from pos_uniformes.services.active_filter_service import ActiveFilterToken


def rebuild_active_filter_chips(
    *,
    container: QWidget,
    layout,
    tokens: Iterable[ActiveFilterToken],
    on_remove: Callable[[ActiveFilterToken], None],
) -> None:
    if layout is None:
        return

    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.deleteLater()

    token_list = list(tokens)
    container.setVisible(bool(token_list))
    for token in token_list:
        button = QPushButton(f"{token.display_text}  ×")
        button.setObjectName("chipButton")
        button.setProperty("active", True)
        button.clicked.connect(lambda _checked=False, active_token=token: on_remove(active_token))
        layout.addWidget(button)
