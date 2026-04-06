from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel

from pos_uniformes.ui.helpers.busy_feedback_helper import BusyFeedbackController, busy_feedback_scope


class BusyFeedbackHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

    def test_scope_updates_status_and_restores_cursor(self) -> None:
        label = QLabel("Estado: listo")

        with busy_feedback_scope(status_label=label, message="Estado: cargando..."):
            self.assertEqual(label.text(), "Estado: cargando...")
            self.assertEqual(
                QApplication.overrideCursor().shape(),
                Qt.CursorShape.WaitCursor,
            )

        self.assertEqual(label.text(), "Estado: listo")
        self.assertIsNone(QApplication.overrideCursor())

    def test_nested_scopes_keep_wait_cursor_until_outer_scope_ends(self) -> None:
        label = QLabel("Estado: listo")

        with busy_feedback_scope(status_label=label, message="Estado: cargando..."):
            with busy_feedback_scope(status_label=label, message="Estado: generando QR..."):
                self.assertEqual(label.text(), "Estado: generando QR...")
                self.assertEqual(
                    QApplication.overrideCursor().shape(),
                    Qt.CursorShape.WaitCursor,
                )
            self.assertEqual(label.text(), "Estado: cargando...")
            self.assertEqual(
                QApplication.overrideCursor().shape(),
                Qt.CursorShape.WaitCursor,
            )

        self.assertEqual(label.text(), "Estado: listo")
        self.assertIsNone(QApplication.overrideCursor())

    def test_controller_exposes_busy_state(self) -> None:
        controller = BusyFeedbackController()
        label = QLabel("Estado: listo")

        self.assertFalse(controller.is_busy)
        with controller.scope(status_label=label, message="Estado: cargando..."):
            self.assertTrue(controller.is_busy)
        self.assertFalse(controller.is_busy)


if __name__ == "__main__":
    unittest.main()
