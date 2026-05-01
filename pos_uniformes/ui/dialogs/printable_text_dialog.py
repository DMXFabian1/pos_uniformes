"""Dialogo reutilizable para mostrar e imprimir texto."""

from __future__ import annotations

from PyQt6.QtCore import QSizeF, Qt
from PyQt6.QtGui import QFontDatabase, QPainter, QPageSize
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QTextEdit, QVBoxLayout, QWidget

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.business_settings_service import BusinessSettingsService
from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
    TICKET_FONT_POINT_SIZE,
    TICKET_PAPER_WIDTH_MM,
    build_ticket_document,
)


def _load_print_preferences() -> tuple[str, int]:
    try:
        with get_session() as session:
            config = BusinessSettingsService.get_or_create(session)
            ticket_printer = config.impresora_tickets or ""
            copies = config.copias_ticket or 1
    except Exception:
        ticket_printer = ""
        copies = 1
    return ticket_printer, copies


def open_printable_text_dialog(parent: QWidget, title: str, content: str) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(620, 520)

    layout = QVBoxLayout()
    editor = QTextEdit()
    editor.setReadOnly(True)
    editor.setDocument(build_ticket_document(content))

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    print_button = buttons.addButton("Imprimir", QDialogButtonBox.ButtonRole.ActionRole)

    def handle_print() -> None:
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            ticket_printer, copies = _load_print_preferences()
            if ticket_printer:
                printer.setPrinterName(ticket_printer)
            printer.setCopyCount(copies)
            printer.setPageSize(QPageSize(QSizeF(TICKET_PAPER_WIDTH_MM, 600.0), QPageSize.Unit.Millimeter))
            printer.setFullPage(True)

            painter = QPainter(printer)
            if not painter.isActive():
                QMessageBox.warning(
                    dialog,
                    "Error de impresión",
                    "No se pudo iniciar el trabajo de impresión.\nVerifica que la impresora esté conectada.",
                )
                return
            font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            font.setPointSize(TICKET_FONT_POINT_SIZE)
            painter.setFont(font)

            # painter.viewport() devuelve el rect imprimible en coordenadas
            # nativas del driver. drawText con TextWordWrap ajusta el texto a
            # ese ancho real, evitando el desfase de unidades de QTextDocument.
            rect = painter.viewport()
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                content,
            )
            painter.end()
        except Exception as exc:
            QMessageBox.warning(dialog, "Error de impresión", f"No se pudo imprimir el ticket:\n{exc}")

    print_button.clicked.connect(handle_print)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(editor)
    layout.addWidget(buttons)
    dialog.setLayout(layout)
    dialog.exec()
