"""Tests del checkbox de juego alterno en el diálogo de impresión.

Con alt_tickets + alt_checkbox_label, el diálogo muestra un checkbox
(desmarcado): al marcarlo, la vista previa y la impresión usan el juego
alterno (p.ej. copia interna con la comisión de la terminal descontada).
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QPushButton,
    QTextEdit,
)

from pos_uniformes.ui.dialogs.printable_text_dialog import open_tickets_print_dialog

_TITLE = "Test alt tickets"


class AltTicketsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.printed: list[str] = []
        self._dialog: QDialog | None = None

    def tearDown(self) -> None:
        if self._dialog is not None:
            self._dialog.reject()
            self._dialog.deleteLater()
            self._dialog = None
        QApplication.processEvents()

    def _open(
        self,
        tickets: list[str],
        alt_tickets: list[str] | None,
        label: str | None = "Descontar comision terminal (6%)",
    ) -> QDialog:
        created: list[QDialog] = []
        with patch.object(
            QDialog, "exec", new=lambda dlg: created.append(dlg) or 0
        ):
            open_tickets_print_dialog(
                None,
                _TITLE,
                tickets,
                print_fn=lambda t: self.printed.append(t) or True,
                alt_tickets=alt_tickets,
                alt_checkbox_label=label,
            )
        self.assertEqual(len(created), 1)
        self._dialog = created[0]
        return self._dialog

    def _checkbox(self, dialog: QDialog) -> QCheckBox | None:
        boxes = dialog.findChildren(QCheckBox)
        return boxes[0] if boxes else None

    def _print_button(self, dialog: QDialog) -> QPushButton:
        buttons = [
            b for b in dialog.findChildren(QPushButton) if "Imprimir" in b.text()
        ]
        self.assertEqual(len(buttons), 1)
        return buttons[0]

    def test_checkbox_present_and_unchecked_with_alt(self) -> None:
        dialog = self._open(["CLIENTE", "COPIA"], ["CLIENTE", "COPIA 6%"])
        checkbox = self._checkbox(dialog)
        self.assertIsNotNone(checkbox)
        self.assertFalse(checkbox.isChecked())
        editor = dialog.findChildren(QTextEdit)[0]
        self.assertEqual(editor.toPlainText(), "CLIENTE\n\nCOPIA")

    def test_no_checkbox_without_alt(self) -> None:
        dialog = self._open(["CLIENTE", "COPIA"], None)
        self.assertIsNone(self._checkbox(dialog))

    def test_toggle_switches_preview(self) -> None:
        dialog = self._open(["CLIENTE", "COPIA"], ["CLIENTE", "COPIA 6%"])
        checkbox = self._checkbox(dialog)
        editor = dialog.findChildren(QTextEdit)[0]
        checkbox.setChecked(True)
        self.assertEqual(editor.toPlainText(), "CLIENTE\n\nCOPIA 6%")
        checkbox.setChecked(False)
        self.assertEqual(editor.toPlainText(), "CLIENTE\n\nCOPIA")

    def test_print_unchecked_uses_base_tickets(self) -> None:
        dialog = self._open(["BASE"], ["ALT"])
        self._print_button(dialog).click()
        # El primer job se imprime sincrono al hacer clic.
        self.assertEqual(self.printed, ["BASE"])

    def test_print_checked_uses_alt_tickets(self) -> None:
        dialog = self._open(["BASE"], ["ALT"])
        self._checkbox(dialog).setChecked(True)
        self._print_button(dialog).click()
        self.assertEqual(self.printed, ["ALT"])

    def test_second_click_while_printing_does_not_start_other_queue(self) -> None:
        # Con 2 tickets, la cola queda imprimiendo (delay entre jobs); un
        # segundo clic con el checkbox cambiado NO debe arrancar la otra cola
        # (imprimía ambos juegos intercalados).
        dialog = self._open(["A", "B"], ["A", "B6"])
        button = self._print_button(dialog)  # su texto cambia al imprimir
        button.click()
        self.assertEqual(self.printed, ["A"])  # primer job síncrono
        self._checkbox(dialog).setChecked(True)
        button.click()
        self.assertEqual(self.printed, ["A"])  # la otra cola no arrancó


if __name__ == "__main__":
    unittest.main()
