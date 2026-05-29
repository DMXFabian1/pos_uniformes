"""Diálogo para previsualizar e imprimir hojas de conteo.

Cada hoja se envía como print job separado con QTimer entre cada una,
permitiendo que el event loop de Qt y el spooler de Windows procesen
cada job antes de enviar el siguiente. Usa la misma configuración
exacta que open_printable_text_dialog (presupuestos/tickets de venta).
"""

from __future__ import annotations

from PyQt6.QtCore import QSizeF, Qt, QTimer
from PyQt6.QtGui import QFontDatabase, QPageLayout, QPainter, QPageSize
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.business_settings_service import BusinessSettingsService
from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
    TICKET_FONT_POINT_SIZE,
    TICKET_PAPER_WIDTH_MM,
)


def _load_print_preferences() -> tuple[str, int]:
    try:
        from pos_uniformes.services.ticket_print_settings_cache_service import (
            load_ticket_print_settings,
        )

        cached_printer, cached_copies = load_ticket_print_settings()
        if cached_printer:
            return cached_printer, cached_copies
    except Exception:
        pass
    try:
        with get_session() as session:
            config = BusinessSettingsService.get_or_create(session)
            return config.impresora_tickets or "", config.copias_ticket or 1
    except Exception:
        return "", 1


def open_conteo_print_dialog(
    parent: QWidget,
    title: str,
    sheets: list[str],
) -> None:
    """Abre diálogo con preview de todas las hojas y botón para imprimir."""
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
    combined = "\n\n".join(sheets)
    editor.setPlainText(combined)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    print_button = buttons.addButton(
        f"Imprimir {len(sheets)} hojas", QDialogButtonBox.ButtonRole.ActionRole
    )

    # Estado de la cola de impresión
    _print_state = {"idx": 0, "errores": 0, "printing": False}

    def _print_next_sheet() -> None:
        """Imprime la siguiente hoja en la cola (llamado por QTimer)."""
        idx = _print_state["idx"]
        if idx >= len(sheets):
            # Todas las hojas enviadas
            ok = len(sheets) - _print_state["errores"]
            if _print_state["errores"]:
                QMessageBox.warning(
                    dialog,
                    "Impresión parcial",
                    f"Se imprimieron {ok} de {len(sheets)} hojas.\n"
                    f"{_print_state['errores']} hoja(s) fallaron.",
                )
            print_button.setText(f"✓ {ok} hojas impresas")
            _print_state["printing"] = False
            QTimer.singleShot(3000, _reset_print_button)
            return

        print_button.setText(f"Imprimiendo {idx + 1}/{len(sheets)}…")

        try:
            # ── Mismo código exacto que printable_text_dialog.py ──
            printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
            printer_name, copies = _load_print_preferences()
            if printer_name:
                printer.setPrinterName(printer_name)
            printer.setCopyCount(copies)
            printer.setPageSize(
                QPageSize(QSizeF(TICKET_PAPER_WIDTH_MM, 600.0), QPageSize.Unit.Millimeter)
            )
            printer.setFullPage(True)
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)

            painter = QPainter()
            if not painter.begin(printer):
                _print_state["errores"] += 1
            else:
                try:
                    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
                    font.setPointSize(TICKET_FONT_POINT_SIZE)
                    font.setBold(True)
                    painter.setFont(font)

                    rect = painter.viewport()
                    painter.drawText(
                        rect,
                        Qt.AlignmentFlag.AlignLeft
                        | Qt.AlignmentFlag.AlignTop
                        | Qt.TextFlag.TextWordWrap,
                        sheets[idx],
                    )
                finally:
                    painter.end()
        except Exception:
            _print_state["errores"] += 1

        _print_state["idx"] += 1
        # Siguiente hoja después de 1.5s — da tiempo al spooler
        QTimer.singleShot(1500, _print_next_sheet)

    def handle_print() -> None:
        if _print_state["printing"]:
            return
        _print_state["printing"] = True
        _print_state["idx"] = 0
        _print_state["errores"] = 0
        print_button.setEnabled(False)
        # Arrancar la primera impresión
        _print_next_sheet()

    def _reset_print_button() -> None:
        try:
            print_button.setText(f"Imprimir {len(sheets)} hojas")
            print_button.setEnabled(True)
        except RuntimeError:
            pass  # diálogo ya cerrado

    print_button.clicked.connect(handle_print)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(editor)
    layout.addWidget(buttons)
    dialog.setLayout(layout)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dialog.exec()
