"""Dialogo reutilizable para mostrar e imprimir texto."""

from __future__ import annotations

from PyQt6.QtCore import QSizeF, Qt
from PyQt6.QtGui import QFontDatabase, QPainter, QPageSize
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTextEdit, QVBoxLayout, QWidget

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
            preferred_printer = config.impresora_preferida or ""
            copies = config.copias_ticket or 1
    except Exception:
        preferred_printer = ""
        copies = 1
    return preferred_printer, copies


def open_printable_text_dialog(parent: QWidget, title: str, content: str) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(620, 520)

    layout = QVBoxLayout()
    editor = QTextEdit()
    editor.setReadOnly(True)
    editor.setPlainText(content)
    editor.setDocument(build_ticket_document(content))

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    print_button = buttons.addButton("Imprimir", QDialogButtonBox.ButtonRole.ActionRole)

    def handle_print() -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        preferred_printer, copies = _load_print_preferences()
        if preferred_printer:
            printer.setPrinterName(preferred_printer)
        printer.setCopyCount(copies)
        printer.setPageSize(QPageSize(QSizeF(TICKET_PAPER_WIDTH_MM, 600.0), QPageSize.Unit.Millimeter))
        printer.setFullPage(True)

        painter = QPainter(printer)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(TICKET_FONT_POINT_SIZE)
        painter.setFont(font)

        # painter.viewport() da el rect imprimible en coordenadas nativas de la
        # impresora. drawText con TextWordWrap ajusta el texto a ese ancho real,
        # evitando el desfase de unidades que ocurre con QTextDocument.setTextWidth.
        rect = painter.viewport()
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            content,
        )
        painter.end()

    print_button.clicked.connect(handle_print)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(editor)
    layout.addWidget(buttons)
    dialog.setLayout(layout)
    dialog.exec()
