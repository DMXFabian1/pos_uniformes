from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from pos_uniformes.ui.dialogs.layaway_payment_dialog import build_layaway_payment_dialog


class _DialogHost(QWidget):
    def _create_modal_dialog(
        self,
        title: str,
        helper_text: str | None = None,
        width: int = 460,
        *,
        expand_to_screen: bool = False,
    ) -> tuple[QDialog, QVBoxLayout]:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(width)
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        return dialog, layout


class LayawayPaymentDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_fixed_amount_dialog_uses_keypad_for_cash_capture(self) -> None:
        host = _DialogHost()

        def fake_exec(dialog: QDialog) -> int:
            combo = next(widget for widget in dialog.findChildren(QComboBox))
            combo.setCurrentIndex(combo.findText("Mixto"))
            next(
                button for button in dialog.findChildren(QPushButton) if button.text() == "Capturar efectivo"
            ).click()
            next(button for button in dialog.findChildren(QPushButton) if button.text() == "5").click()
            next(button for button in dialog.findChildren(QPushButton) if button.text() == "0").click()
            return int(QDialog.DialogCode.Accepted)

        with patch("pos_uniformes.ui.dialogs.layaway_payment_dialog.QDialog.exec", new=fake_exec):
            payload = build_layaway_payment_dialog(
                host,
                title="Liquidar y entregar apartado",
                initial_amount=Decimal("87.80"),
                fixed_amount=True,
            )

        self.assertIsNotNone(payload)
        self.assertEqual(payload.amount, Decimal("87.80"))
        self.assertEqual(payload.payment_method, "Mixto")
        self.assertEqual(payload.cash_amount, Decimal("50.00"))

    def test_fixed_amount_cash_dialog_allows_received_amount_and_shows_change(self) -> None:
        host = _DialogHost()
        observed_change = {"text": ""}

        def fake_exec(dialog: QDialog) -> int:
            next(
                button for button in dialog.findChildren(QPushButton) if button.text() == "Capturar recibido"
            ).click()
            next(button for button in dialog.findChildren(QPushButton) if button.text() == "$200").click()
            observed_change["text"] = next(
                label for label in dialog.findChildren(QLabel) if label.objectName() == "cashierChangeValue"
            ).text()
            return int(QDialog.DialogCode.Accepted)

        with patch("pos_uniformes.ui.dialogs.layaway_payment_dialog.QDialog.exec", new=fake_exec):
            payload = build_layaway_payment_dialog(
                host,
                title="Liquidar y entregar apartado",
                initial_amount=Decimal("151.50"),
                fixed_amount=True,
            )

        self.assertIsNotNone(payload)
        self.assertEqual(payload.payment_method, "Efectivo")
        self.assertEqual(payload.cash_amount, Decimal("151.50"))
        self.assertEqual(observed_change["text"], "$48.50")


if __name__ == "__main__":
    unittest.main()
