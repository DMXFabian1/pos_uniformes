"""Dialogo reutilizable para mostrar e imprimir tickets de 80 mm.

- open_printable_text_dialog: un solo documento (presupuestos, etc.).
- open_tickets_print_dialog : uno o varios tickets; un solo "Imprimir" los
  manda todos como jobs separados (autocut entre cada uno).

Ambos comparten la misma cola segura (TicketPrintQueue): si se cierra el
dialogo mientras hay un QTimer pendiente, no se tocan widgets ya destruidos.
"""

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
)
from pos_uniformes.ui.helpers.ticket_print_queue import TicketPrintQueue


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


def _print_ticket_job(content: str) -> bool:
    """Envia un ticket a la impresora como un job independiente.

    Devuelve True si el job se inicio correctamente. Cada llamada crea su
    propio QPrinter -> el autocutter corta entre tickets.
    """
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
        return False
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
    return True


# Nombre público reutilizable por el despachador del satélite: imprime un ticket
# de texto plano a la impresora térmica configurada. Devuelve True si arrancó.
print_ticket_text = _print_ticket_job


def _build_ticket_editor(content: str) -> QTextEdit:
    editor = QTextEdit()
    editor.setReadOnly(True)
    mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
    editor.setStyleSheet(
        f'QTextEdit {{ font-family: "{mono_family}"; font-size: {TICKET_FONT_POINT_SIZE}pt;'
        f" font-weight: bold; }}"
    )
    editor.setPlainText(content)
    return editor


def open_printable_text_dialog(parent: QWidget, title: str, content: str) -> None:
    """Muestra un texto e imprime un unico ticket (un job)."""
    open_tickets_print_dialog(parent, title, [content])


def open_tickets_print_dialog(
    parent: QWidget,
    title: str,
    tickets: list[str],
    *,
    unit_label: str = "ticket",
) -> None:
    """Muestra uno o varios tickets en una sola vista.

    Un solo clic en "Imprimir" manda todos los tickets como jobs separados
    (cada uno se corta por el autocutter). Reemplaza el flujo anterior de un
    dialogo por copia, que obligaba a imprimir dos veces.

    unit_label permite reutilizar el dialogo para otros documentos del mismo
    formato (p.ej. "hoja" para las hojas de conteo).
    """
    tickets = [t for t in tickets if t and t.strip()]
    if not tickets:
        return

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(620, 520)

    layout = QVBoxLayout()
    editor = _build_ticket_editor("\n\n".join(tickets))

    n = len(tickets)
    idle_label = "Imprimir" if n == 1 else f"Imprimir {n} {unit_label}s"
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    print_button = buttons.addButton(idle_label, QDialogButtonBox.ButtonRole.ActionRole)

    def _set_status(text: str) -> None:
        print_button.setText(text)
        print_button.setEnabled(text == idle_label)

    def _report(ok: int, errors: int) -> None:
        if not errors:
            return
        if ok == 0:
            msg = "No se pudo imprimir.\nVerifica que la impresora este conectada."
        else:
            msg = f"Se imprimieron {ok} de {n} {unit_label}s.\n{errors} fallaron."
        QMessageBox.warning(dialog, "Error de impresion", msg)

    queue = TicketPrintQueue(
        tickets,
        print_fn=_print_ticket_job,
        schedule=QTimer.singleShot,
        on_status=_set_status,
        on_done=_report,
        idle_label=idle_label,
    )

    print_button.clicked.connect(queue.start)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    # Al cerrar el dialogo, la cola deja de tocar sus widgets (evita crash).
    dialog.finished.connect(lambda _result: queue.close())

    layout.addWidget(editor)
    layout.addWidget(buttons)
    dialog.setLayout(layout)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dialog.exec()
