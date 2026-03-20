"""Helpers reutilizables para campos de fecha con calendario amigable."""

from __future__ import annotations

from PyQt6.QtCore import QDate, QEvent, QObject
from PyQt6.QtWidgets import QDateEdit


class _DatePopupEventFilter(QObject):
    def __init__(self, editor: QDateEdit) -> None:
        super().__init__(editor)
        self._editor = editor

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show:
            calendar = self._editor.calendarWidget()
            target_date = self._editor.date()
            if target_date == self._editor.minimumDate():
                target_date = QDate.currentDate()
            calendar.setSelectedDate(target_date)
            calendar.setCurrentPage(target_date.year(), target_date.month())
        return super().eventFilter(watched, event)


def configure_friendly_date_edit(
    field: QDateEdit,
    *,
    placeholder_text: str | None = None,
    minimum_date: QDate | None = None,
    initial_date: QDate | None = None,
    minimum_width: int | None = None,
) -> None:
    field.setCalendarPopup(True)
    field.setDisplayFormat("dd/MM/yyyy")
    if minimum_date is not None:
        field.setMinimumDate(minimum_date)
    if placeholder_text is not None:
        field.setSpecialValueText(placeholder_text)
    if initial_date is not None:
        field.setDate(initial_date)
    if minimum_width is not None:
        field.setMinimumWidth(minimum_width)
    popup_filter = _DatePopupEventFilter(field)
    field.calendarWidget().installEventFilter(popup_filter)
    field._popup_event_filter = popup_filter
