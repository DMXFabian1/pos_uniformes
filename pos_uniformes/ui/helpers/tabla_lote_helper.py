"""Piezas de tabla compartidas por los diálogos de lote de Inventario.

Salieron de `ui/main_window.py` tal cual (2026-11-19); `main_window` las sigue
importando con su nombre viejo (`_table_item`, `_TableSpinTabNavigator`, …).
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QTableWidgetItem, QWidget


def table_item(value: object) -> QTableWidgetItem:
    item = QTableWidgetItem("" if value is None else str(value))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


class TableSpinTabNavigator(QObject):
    def __init__(
        self,
        *,
        anchor_before: QWidget | None = None,
        anchor_after: QWidget | None = None,
    ) -> None:
        super().__init__(anchor_after or anchor_before)
        self._anchor_before = anchor_before
        self._anchor_after = anchor_after
        self._inputs: list[QWidget] = []

    def set_inputs(self, inputs: list[QWidget]) -> None:
        self._inputs = list(inputs)
        for input_widget in self._inputs:
            input_widget.installEventFilter(self)
            editor = self._editor_for(input_widget)
            if editor is not None:
                editor.installEventFilter(self)
        if not self._inputs:
            return
        if self._anchor_before is not None:
            QWidget.setTabOrder(self._anchor_before, self._inputs[0])
        previous_widget = self._inputs[0]
        for input_widget in self._inputs[1:]:
            QWidget.setTabOrder(previous_widget, input_widget)
            previous_widget = input_widget
        if self._anchor_after is not None:
            QWidget.setTabOrder(previous_widget, self._anchor_after)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        key = event.key()
        if key not in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            return super().eventFilter(watched, event)
        direction = -1 if key == Qt.Key.Key_Backtab else 1
        owner_widget = self._resolve_input_owner(watched)
        if owner_widget is None:
            return super().eventFilter(watched, event)
        return self._move_focus(owner_widget, direction)

    def _resolve_input_owner(self, watched: QObject) -> QWidget | None:
        if watched in self._inputs:
            return watched if isinstance(watched, QWidget) else None
        for input_widget in self._inputs:
            if self._editor_for(input_widget) is watched:
                return input_widget
        return None

    @staticmethod
    def _editor_for(widget: QWidget) -> QWidget | None:
        line_edit = getattr(widget, "lineEdit", None)
        if callable(line_edit):
            return line_edit()
        return None

    def _move_focus(self, source_widget: QWidget, direction: int) -> bool:
        try:
            current_index = self._inputs.index(source_widget)
        except ValueError:
            return False
        if direction > 0:
            if current_index + 1 < len(self._inputs):
                target = self._inputs[current_index + 1]
            else:
                target = self._anchor_after
        else:
            if current_index - 1 >= 0:
                target = self._inputs[current_index - 1]
            else:
                target = self._anchor_before
        if not isinstance(target, QWidget):
            return False
        target.setFocus(Qt.FocusReason.TabFocusReason)
        editor = self._editor_for(target)
        if editor is not None and hasattr(editor, "selectAll"):
            editor.selectAll()
        return True


def set_table_badge_style(item: QTableWidgetItem, tone: str, *, con_fondo: bool = True) -> None:
    palette = {
        "positive": ("#e5f2eb", "#245241"),
        "warning": ("#fbf0cf", "#8a5a00"),
        "danger": ("#f8dfd9", "#9a2f22"),
        "reserved": ("#e5edf6", "#2d5068"),
        "muted": ("#ece8e1", "#6e675f"),
    }
    background, foreground = palette.get(tone, palette["muted"])
    if con_fondo:
        item.setBackground(QColor(background))
    item.setForeground(QColor(foreground))
    item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))


def build_bulk_selection_label(selected_ids: list[int], matched_rows: list[dict[str, object]]) -> str:
    matched = len(matched_rows)
    total = len(selected_ids)
    if total > matched:
        return f"Filas seleccionadas ({matched} de {total} — {total - matched} no coinciden con el filtro actual)"
    return f"Filas seleccionadas ({matched})"
