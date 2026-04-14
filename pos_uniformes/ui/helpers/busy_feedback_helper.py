"""Helpers para mostrar estados de carga visibles en UI."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel


@dataclass
class BusyFeedbackState:
    active_scopes: int = 0

    @property
    def is_busy(self) -> bool:
        return self.active_scopes > 0


class BusyFeedbackScope(AbstractContextManager["BusyFeedbackScope"]):
    def __init__(
        self,
        *,
        controller: "BusyFeedbackController",
        status_label: QLabel | None,
        message: str,
    ) -> None:
        self._controller = controller
        self._status_label = status_label
        self._message = message
        self._previous_text = status_label.text() if status_label is not None else ""

    def __enter__(self) -> "BusyFeedbackScope":
        self._controller._push_busy_state()
        if self._status_label is not None:
            self._status_label.setText(self._message)
        QApplication.processEvents()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if self._status_label is not None:
            self._status_label.setText(self._previous_text)
        QApplication.processEvents()
        self._controller._pop_busy_state()
        return None


class BusyFeedbackController:
    def __init__(self) -> None:
        self._state = BusyFeedbackState()

    @property
    def is_busy(self) -> bool:
        return self._state.is_busy

    def scope(self, *, status_label: QLabel | None, message: str) -> BusyFeedbackScope:
        return BusyFeedbackScope(controller=self, status_label=status_label, message=message)

    def _push_busy_state(self) -> None:
        self._state.active_scopes += 1
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    def _pop_busy_state(self) -> None:
        if self._state.active_scopes > 0:
            self._state.active_scopes -= 1
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()


_DEFAULT_CONTROLLER = BusyFeedbackController()


def busy_feedback_scope(*, status_label: QLabel | None, message: str) -> BusyFeedbackScope:
    return _DEFAULT_CONTROLLER.scope(status_label=status_label, message=message)
