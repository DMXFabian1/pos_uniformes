"""Helper reutilizable para popup de sugerencias en inputs de busqueda."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QPoint, Qt
from PyQt6.QtWidgets import QAbstractItemView, QLineEdit, QListWidget, QListWidgetItem


def merge_search_completion(current_text: str, completion: str) -> str:
    current_value = str(current_text or "")
    trimmed_value = current_value.rstrip()
    if not trimmed_value:
        return completion

    last_space = trimmed_value.rfind(" ")
    if last_space == -1:
        return completion
    return f"{trimmed_value[: last_space + 1]}{completion}"


class _SearchSuggestionPopup(QListWidget):
    def __init__(self, line_edit: QLineEdit) -> None:
        super().__init__(line_edit.window())
        self._line_edit = line_edit
        self.setWindowFlag(Qt.WindowType.Popup, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)

    def show_for_line_edit(self) -> None:
        row_count = self.count()
        if row_count <= 0 or not self._line_edit.isVisible():
            self.hide()
            return

        row_height = max(self.sizeHintForRow(0), 24)
        visible_rows = min(row_count, 8)
        frame = self.frameWidth() * 2
        popup_height = (row_height * visible_rows) + frame
        popup_width = max(self._line_edit.width(), 260)
        bottom_left = self._line_edit.mapToGlobal(QPoint(0, self._line_edit.height()))
        self.setGeometry(bottom_left.x(), bottom_left.y(), popup_width, popup_height)
        self.show()
        if self.window().isVisible():
            self.raise_()


class _SearchSuggestionController(QObject):
    def __init__(self, line_edit: QLineEdit) -> None:
        super().__init__(line_edit)
        self._line_edit = line_edit
        self._anchor_text = line_edit.text()
        self._popup = _SearchSuggestionPopup(line_edit)
        self._popup.itemClicked.connect(self._handle_item_clicked)
        self._line_edit.textEdited.connect(self._handle_text_edited)
        self._line_edit.installEventFilter(self)
        self._popup.installEventFilter(self)
        self._suggestions: list[str] = []
        self._line_edit.setCompleter(None)

    @property
    def popup(self) -> _SearchSuggestionPopup:
        return self._popup

    def _handle_text_edited(self, text: str) -> None:
        self._anchor_text = text

    def _handle_item_clicked(self, item: QListWidgetItem) -> None:
        self.commit_completion(item.text())

    def update_suggestions(self, suggestions: list[str]) -> None:
        self._suggestions = suggestions
        self._popup.clear()
        for suggestion in suggestions:
            self._popup.addItem(suggestion)

        if not suggestions or not self._line_edit.hasFocus() or not self._anchor_text.strip():
            self._popup.hide()
            return

        self._popup.setCurrentRow(0)
        self._popup.show_for_line_edit()

    def commit_completion(self, completion: str) -> None:
        if not completion:
            return
        merged_value = merge_search_completion(self._anchor_text, completion)
        self._line_edit.setText(merged_value)
        self._line_edit.setCursorPosition(len(merged_value))
        self._anchor_text = merged_value
        self._popup.hide()

    def _move_selection(self, step: int) -> bool:
        row_count = self._popup.count()
        if row_count <= 0:
            return True

        current_row = self._popup.currentRow()
        if current_row < 0:
            next_row = 0 if step > 0 else row_count - 1
        else:
            next_row = max(0, min(current_row + step, row_count - 1))

        self._popup.setCurrentRow(next_row)
        self._popup.scrollToItem(self._popup.item(next_row))
        return True

    def commit_current_completion(self) -> bool:
        current_item = self._popup.currentItem()
        if current_item is None and self._popup.count() > 0:
            current_item = self._popup.item(0)
        if current_item is None:
            self._popup.hide()
            return True
        self.commit_completion(current_item.text())
        return True

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if watched is self._line_edit:
            if event.type() == QEvent.Type.FocusOut:
                self._popup.hide()
                return False

            if event.type() != QEvent.Type.KeyPress or not self._popup.isVisible():
                return False

            key = event.key()
            if key == Qt.Key.Key_Down:
                return self._move_selection(1)
            if key == Qt.Key.Key_Up:
                return self._move_selection(-1)
            if key == Qt.Key.Key_PageDown:
                return self._move_selection(5)
            if key == Qt.Key.Key_PageUp:
                return self._move_selection(-5)
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                return self.commit_current_completion()
            if key == Qt.Key.Key_Escape:
                self._popup.hide()
                return True
            return False

        if watched is self._popup and event.type() == QEvent.Type.MouseButtonPress:
            item = self._popup.itemAt(event.position().toPoint())
            if item is not None:
                self.commit_completion(item.text())
                return True

        return False


def apply_search_suggestions(line_edit: QLineEdit, suggestions: list[str]) -> None:
    controller = getattr(line_edit, "_search_suggestion_controller", None)
    if not isinstance(controller, _SearchSuggestionController):
        controller = _SearchSuggestionController(line_edit)
        setattr(line_edit, "_search_suggestion_controller", controller)

    controller.update_suggestions(suggestions)
