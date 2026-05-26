"""Dialogo reutilizable para mostrar e imprimir texto."""

from __future__ import annotations

from PyQt6.QtCore import QSizeF, Qt, QTimer
from PyQt6.QtGui import QFontDatabase, QPageLayout, QPainter, QPageSize
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
    # El cache local (menu admin del satelite) siempre tiene prioridad.
    # La BD solo se usa si nunca se configuro una impresora local.
    try:
        from pos_uniformes.services.ticket_print_settings_cache_service import load_ticket_print_settings
        cached_printer, cached_copies = load_ticket_print_settings()
        if cached_printer:
            return cached_printer, cached_copies
    except Exception:
        pass
    # Fallback: BD (primer arranque sin configuracion local)
    try:
        with get_session() as session:
            config = BusinessSettingsService.get_or_create(session)
            return config.impresora_tickets or "", config.copias_ticket or 1
    except Exception:
        return "", 1


def open_printable_text_dialog(parent: QWidget, title: str, content: str) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(620, 520)

    layout = QVBoxLayout()
    editor = QTextEdit()
    editor.setReadOnly(True)
    mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
    editor.setStyleSheet(
        f'QTextEdit {{ font-family: "{mono_family}"; font-size: {TICKET_FONT_POINT_SIZE}pt;'
        f" font-weight: bold; }}"
    )
    editor.setPlainText(content)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    print_button = buttons.addButton("Imprimir", QDialogButtonBox.ButtonRole.ActionRole)

    _COOLDOWN_MS = 3000  # ms antes de re-habilitar el botón tras imprimir

    def handle_print() -> None:
        # Bloquear el botón inmediatamente para evitar doble impresión
        print_button.setEnabled(False)
        print_button.setText("Imprimiendo…")

        try:
            printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
            ticket_printer, copies = _load_print_preferences()
            if ticket_printer:
                printer.setPrinterName(ticket_printer)
            printer.setCopyCount(copies)
            printer.setPageSize(QPageSize(QSizeF(TICKET_PAPER_WIDTH_MM, 600.0), QPageSize.Unit.Millimeter))
            printer.setFullPage(True)
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)

            painter = QPainter()
            if not painter.begin(printer):
                QMessageBox.warning(
                    dialog,
                    "Error de impresión",
                    "No se pudo iniciar el trabajo de impresión.\nVerifica que la impresora esté conectada.",
                )
                _reset_print_button()
                return
            try:
                font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
                font.setPointSize(TICKET_FONT_POINT_SIZE)
                font.setBold(True)
                painter.setFont(font)

                rect = painter.viewport()
                painter.drawText(
                    rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                    content,
                )
            finally:
                painter.end()
            # Impresión exitosa — mostrar confirmación antes de re-habilitar
            print_button.setText("✓ Impreso")
            QTimer.singleShot(_COOLDOWN_MS, _reset_print_button)
        except Exception as exc:
            QMessageBox.warning(dialog, "Error de impresión", f"No se pudo imprimir el ticket:\n{exc}")
            _reset_print_button()

    def _reset_print_button() -> None:
        print_button.setText("Imprimir")
        print_button.setEnabled(True)

    print_button.clicked.connect(handle_print)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(editor)
    layout.addWidget(buttons)
    dialog.setLayout(layout)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dialog.exec()
