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

    def test_on_printed_solo_cuando_arranca_la_impresion(self) -> None:
        from unittest.mock import MagicMock

        on_printed = MagicMock()
        created: list[QDialog] = []
        with patch.object(QDialog, "exec", new=lambda dlg: created.append(dlg) or 0):
            open_tickets_print_dialog(
                None,
                _TITLE,
                ["BASE"],
                print_fn=lambda t: self.printed.append(t) or True,
                on_printed=on_printed,
            )
        self._dialog = created[0]
        # Abrir (y cerrar) sin imprimir NO dispara el efecto.
        on_printed.assert_not_called()
        self._print_button(self._dialog).click()
        on_printed.assert_called_once()

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


class TotalBadgeTests(unittest.TestCase):
    """Recuadro con el TOTAL arriba a la derecha del diálogo de impresión."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_extrae_total_de_venta_y_apartado(self) -> None:
        from pos_uniformes.ui.dialogs.printable_text_dialog import total_del_ticket

        venta = "│ Subtotal:      $285.00 │\n│ TOTAL A PAGAR:   $285.00 │"
        apartado = "│ TOTAL:        $1,180.00 │\n│ Apartado minimo (25%): $295.00 │"
        self.assertEqual(total_del_ticket(venta), "$285.00")
        self.assertEqual(total_del_ticket(apartado), "$1,180.00")
        self.assertIsNone(total_del_ticket("hoja de conteo sin totales"))
        self.assertIsNone(total_del_ticket("│ Subtotal:      $285.00 │"))

    def test_dialogo_muestra_recuadro_solo_si_hay_total(self) -> None:
        from PyQt6.QtWidgets import QLabel

        creados: list[QDialog] = []
        with patch.object(QDialog, "exec", new=lambda dlg: creados.append(dlg) or 0):
            open_tickets_print_dialog(
                None, "Ticket de venta", ["│ TOTAL A PAGAR:   $285.00 │"],
                print_fn=lambda t: True,
            )
            open_tickets_print_dialog(
                None, "Hojas de conteo", ["hoja 1"], print_fn=lambda t: True,
            )
        con, sin = creados
        badges = [l for l in con.findChildren(QLabel) if l.objectName() == "ticketTotal"]
        self.assertEqual(len(badges), 1)
        self.assertIn("$285.00", badges[0].text())
        self.assertFalse(
            [l for l in sin.findChildren(QLabel) if l.objectName() == "ticketTotal"]
        )
        for d in creados:
            d.reject(); d.deleteLater()
        QApplication.processEvents()


class RegresarButtonTests(unittest.TestCase):
    """"← Regresar" cierra sin imprimir y vuelve a la pregunta anterior."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _abrir(self, on_back):
        printed: list[str] = []
        notified: list[bool] = []

        def _exec(dlg):
            botones = [b for b in dlg.findChildren(QPushButton) if "Regresar" in b.text()]
            if botones:
                botones[0].click()
            return 0

        with patch.object(QDialog, "exec", new=_exec):
            open_tickets_print_dialog(
                None, _TITLE, ["ticket"], print_fn=lambda t: printed.append(t) or True,
                on_printed=lambda: notified.append(True), on_back=on_back,
            )
        QApplication.processEvents()
        return printed, notified

    def test_regresar_llama_on_back_sin_imprimir_ni_registrar(self) -> None:
        vueltas: list[bool] = []
        printed, notified = self._abrir(lambda: vueltas.append(True))
        self.assertEqual(vueltas, [True])
        self.assertEqual(printed, [])
        self.assertEqual(notified, [])

    def test_sin_on_back_no_hay_boton(self) -> None:
        botones: list[str] = []

        def _exec(dlg):
            botones.extend(b.text() for b in dlg.findChildren(QPushButton))
            return 0

        with patch.object(QDialog, "exec", new=_exec):
            open_tickets_print_dialog(None, _TITLE, ["ticket"], print_fn=lambda t: True)
        self.assertFalse(any("Regresar" in t for t in botones))
        self.assertTrue(any("Cerrar" in t for t in botones))
