from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QDialog, QLineEdit, QVBoxLayout

from pos_uniformes.ui.helpers.scanner_enter_guard import (
    ScannerBurstDetector,
    ScannerEnterGuard,
)


class ScannerBurstDetectorTests(unittest.TestCase):
    """Lógica pura con timestamps inyectados — sin sleeps ni Qt."""

    def test_scanner_burst_swallows_enter(self) -> None:
        detector = ScannerBurstDetector()
        # "EMP:VEND-1" a ~15ms por tecla, como escáner HID real
        for i in range(10):
            detector.feed_char(1000.0 + i * 15.0)
        self.assertTrue(detector.should_swallow_enter(1000.0 + 10 * 15.0))

    def test_human_typing_keeps_enter(self) -> None:
        detector = ScannerBurstDetector()
        # Tecleo manual: ~200ms entre teclas
        for i in range(10):
            detector.feed_char(1000.0 + i * 200.0)
        self.assertFalse(detector.should_swallow_enter(1000.0 + 10 * 200.0))

    def test_enter_without_chars_passes(self) -> None:
        detector = ScannerBurstDetector()
        self.assertFalse(detector.should_swallow_enter(1000.0))

    def test_enter_long_after_burst_passes(self) -> None:
        detector = ScannerBurstDetector()
        for i in range(10):
            detector.feed_char(1000.0 + i * 15.0)
        # Enter 500ms después de la última tecla: ya no es del escáner
        self.assertFalse(detector.should_swallow_enter(1000.0 + 10 * 15.0 + 500.0))

    def test_short_burst_passes(self) -> None:
        detector = ScannerBurstDetector()
        # 2 teclas rápidas (p.ej. doble Enter accidental con una letra) no bastan
        detector.feed_char(1000.0)
        detector.feed_char(1010.0)
        self.assertFalse(detector.should_swallow_enter(1020.0))

    def test_state_resets_after_enter(self) -> None:
        detector = ScannerBurstDetector()
        for i in range(10):
            detector.feed_char(1000.0 + i * 15.0)
        self.assertTrue(detector.should_swallow_enter(1150.0))
        # Un segundo Enter inmediato ya no se traga (estado limpio)
        self.assertFalse(detector.should_swallow_enter(1160.0))


def _char_event(char: str) -> QKeyEvent:
    return QKeyEvent(
        QEvent.Type.KeyPress, ord(char.upper()), Qt.KeyboardModifier.NoModifier, char
    )


def _enter_event() -> QKeyEvent:
    return QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Return.value,
        Qt.KeyboardModifier.NoModifier,
        "\r",
    )


class ScannerEnterGuardQtTests(unittest.TestCase):
    """El filtro solo actúa sobre el diálogo y sus hijos."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _make_dialog(self) -> tuple[QDialog, QLineEdit, ScannerEnterGuard]:
        dialog = QDialog()
        layout = QVBoxLayout()
        field = QLineEdit()
        layout.addWidget(field)
        dialog.setLayout(layout)
        guard = ScannerEnterGuard(dialog)
        return dialog, field, guard

    def test_swallows_enter_after_burst_on_dialog_child(self) -> None:
        dialog, field, guard = self._make_dialog()
        # Ráfaga en proceso: los eventos sintéticos llegan en microsegundos
        for char in "EMP:VEND-1":
            self.assertFalse(guard.eventFilter(field, _char_event(char)))
        self.assertTrue(guard.eventFilter(field, _enter_event()))
        dialog.deleteLater()

    def test_enter_alone_passes_through(self) -> None:
        dialog, field, guard = self._make_dialog()
        self.assertFalse(guard.eventFilter(field, _enter_event()))
        dialog.deleteLater()

    def test_foreign_widget_is_ignored(self) -> None:
        dialog, _field, guard = self._make_dialog()
        outsider = QLineEdit()  # widget fuera del diálogo
        for char in "EMP:VEND-1":
            self.assertFalse(guard.eventFilter(outsider, _char_event(char)))
        # El Enter del escáner en otro widget no es asunto de este guard
        self.assertFalse(guard.eventFilter(outsider, _enter_event()))
        outsider.deleteLater()
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
