"""Helpers de UI para captura numerica por teclado en dialogs de cobro."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QDialog, QPushButton


def append_keypad_text(current: str, value: str) -> str:
    normalized_current = current or "0.00"
    if normalized_current == "0.00" and value != ".":
        normalized_current = ""
    if value == "." and "." in normalized_current:
        return normalized_current or "0"
    return (normalized_current + value) or "0"


def clear_keypad_text() -> str:
    return "0.00"


def backspace_keypad_text(current: str) -> str:
    normalized_current = (current or "0.00")[:-1]
    if not normalized_current or normalized_current == "-":
        return "0.00"
    return normalized_current


def parse_keypad_amount_text(current: str) -> Decimal:
    normalized_current = (current or "0.00").strip().replace(",", ".")
    if normalized_current in {"", ".", "-"}:
        return Decimal("0.00")
    try:
        return Decimal(normalized_current).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def install_keypad_shortcuts(
    *,
    dialog: QDialog,
    accept_button: QPushButton,
    reject_button: QPushButton,
    append_value: Callable[[str], None],
    clear_value: Callable[[], None],
    backspace_value: Callable[[], None],
) -> None:
    shortcuts: list[QShortcut] = []

    def register(sequence: QKeySequence | str, callback: Callable[[], None]) -> None:
        shortcut = QShortcut(QKeySequence(sequence), dialog)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)
        shortcuts.append(shortcut)

    for digit in "0123456789":
        register(digit, lambda value=digit: append_value(value))
    register(".", lambda: append_value("."))
    register(",", lambda: append_value("."))
    register("Backspace", backspace_value)
    register("Delete", clear_value)
    register(QKeySequence(Qt.Key.Key_Return), accept_button.click)
    register(QKeySequence(Qt.Key.Key_Enter), accept_button.click)
    register("Escape", reject_button.click)

    dialog._keypad_shortcuts = shortcuts  # type: ignore[attr-defined]
