"""Diálogo para previsualizar e imprimir hojas de conteo.

Cada hoja se envía como un print job separado para que la impresora
térmica corte entre cada producto.
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


def _print_single_sheet(sheet_text: str, printer_name: str, copies: int) -> None:
    """Envía una hoja como un print job independiente.

    Usa altura generosa (rollo continuo) — la térmica solo avanza lo necesario.
    """
    # Altura basada en líneas: ~4mm por línea a 8pt + margen
    num_lines = sheet_text.count("\n") + 1
    height_mm = max(num_lines * 4.0 + 20, 120)

    printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
    if printer_name:
        printer.setPrinterName(printer_name)
    printer.setCopyCount(copies)
    printer.setPageSize(
        QPageSize(QSizeF(TICKET_PAPER_WIDTH_MM, height_mm), QPageSize.Unit.Millimeter)
    )
    printer.setFullPage(True)
    printer.setPageOrientation(QPageLayout.Orientation.Portrait)

    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("No se pudo iniciar el trabajo de impresión.")
    try:
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(TICKET_FONT_POINT_SIZE)
        font.setBold(True)
        painter.setFont(font)

        rect = painter.viewport()
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            sheet_text,
        )
    finally:
        painter.end()


def open_conteo_print_dialog(
    parent: QWidget,
    title: str,
    sheets: list[str],
) -> None:
    """Abre diálogo con preview de todas las hojas y botón para imprimir.

    Al imprimir, cada hoja se envía como un print job separado para que
    la impresora térmica corte entre cada producto.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(620, 520)

    layout = QVBoxLayout()

    # Preview: todas las hojas concatenadas
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

    _COOLDOWN_MS = 3000

    def handle_print() -> None:
        print_button.setEnabled(False)
        print_button.setText("Imprimiendo…")

        try:
            printer_name, copies = _load_print_preferences()
            errores = 0
            for i, sheet in enumerate(sheets):
                try:
                    _print_single_sheet(sheet, printer_name, copies)
                except Exception:
                    errores += 1

            if errores:
                QMessageBox.warning(
                    dialog,
                    "Impresión parcial",
                    f"Se imprimieron {len(sheets) - errores} de {len(sheets)} hojas.\n"
                    f"{errores} hoja(s) fallaron.",
                )
            print_button.setText(f"✓ {len(sheets) - errores} hojas impresas")
            QTimer.singleShot(_COOLDOWN_MS, _reset_print_button)
        except Exception as exc:
            QMessageBox.warning(
                dialog, "Error de impresión", f"No se pudo imprimir:\n{exc}"
            )
            _reset_print_button()

    def _reset_print_button() -> None:
        print_button.setText(f"Imprimir {len(sheets)} hojas")
        print_button.setEnabled(True)

    print_button.clicked.connect(handle_print)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(editor)
    layout.addWidget(buttons)
    dialog.setLayout(layout)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dialog.exec()
