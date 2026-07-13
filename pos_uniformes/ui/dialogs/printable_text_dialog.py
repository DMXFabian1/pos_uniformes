"""Dialogo reutilizable para mostrar e imprimir tickets de 80 mm.

- open_printable_text_dialog: un solo documento (presupuestos, etc.).
- open_tickets_print_dialog : uno o varios tickets; un solo "Imprimir" los
  manda todos como jobs separados (autocut entre cada uno).

Ambos comparten la misma cola segura (TicketPrintQueue): si se cierra el
dialogo mientras hay un QTimer pendiente, no se tocan widgets ya destruidos.
"""

from __future__ import annotations

from PyQt6.QtCore import QSizeF, Qt, QTimer
from PyQt6.QtGui import QFontDatabase, QImage, QPageLayout, QPainter, QPageSize
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QTextEdit, QVBoxLayout, QWidget

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.business_settings_service import BusinessSettingsService
from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
    TICKET_FONT_POINT_SIZE,
    TICKET_PAPER_WIDTH_MM,
)
from pos_uniformes.ui.helpers.ticket_print_queue import TicketPrintQueue

# Avance extra (mm) después del contenido para que la cuchilla del autocutter
# —que corta ~10 mm por encima del cabezal— no recorte la última línea. Con la
# página de alto dinámico, este es el único "colchón" de papel entre el fin del
# ticket y el corte, en vez de los 600 mm fijos de antes que cortaban a destiempo.
TICKET_BOTTOM_FEED_MM = 12.0
# DPI de referencia para medir el alto del texto (ScreenResolution ≈ 96 dpi). El
# alto físico en mm es independiente del dpi (la fuente está en puntos), así que
# medir a 96 dpi coincide con lo que dibuja drawText en la impresora.
_MEASURE_DPI = 96


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


def _ticket_page_height_mm(content: str) -> float:
    """Alto de página (mm) = alto REAL del texto (como lo dibuja drawText) + colchón.

    Antes la página era fija de 600 mm y el driver cortaba según SU longitud de
    papel: hojas largas se cortaban a la mitad. Se mide con boundingRect sobre un
    QImage con el MISMO ancho (80 mm) y flags que usa drawText, así la página
    coincide exacto con lo impreso y el autocutter corta justo al final. (Medir
    con QTextDocument daba de más: envolvía las líneas de caja a un ancho menor.)
    """
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(TICKET_FONT_POINT_SIZE)
    font.setBold(True)

    ancho_px = max(1, round(TICKET_PAPER_WIDTH_MM / 25.4 * _MEASURE_DPI))
    lienzo = QImage(ancho_px, 8, QImage.Format.Format_ARGB32)  # solo aporta dpi/fuente
    lienzo.setDotsPerMeterX(round(_MEASURE_DPI / 0.0254))
    lienzo.setDotsPerMeterY(round(_MEASURE_DPI / 0.0254))

    medidor = QPainter(lienzo)
    try:
        medidor.setFont(font)
        flags = (
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap
        )
        bound = medidor.boundingRect(0, 0, ancho_px, 100_000, flags, content)
    finally:
        medidor.end()

    alto_mm = bound.height() / _MEASURE_DPI * 25.4
    return alto_mm + TICKET_BOTTOM_FEED_MM


def _print_ticket_job(content: str) -> bool:
    """Envia un ticket a la impresora como un job independiente.

    Cada llamada crea su propio QPrinter. Lo ÚNICO que cambia respecto al
    comportamiento histórico es el alto de página (ahora dinámico, = contenido,
    para que el autocutter corte justo al final). El renderizado sigue siendo el
    mismo `drawText` de siempre para NO mover el formato del ticket/hoja.
    """
    printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
    ticket_printer, copies = _load_print_preferences()
    if ticket_printer:
        printer.setPrinterName(ticket_printer)
    printer.setCopyCount(copies)
    printer.setPageSize(
        QPageSize(
            QSizeF(TICKET_PAPER_WIDTH_MM, _ticket_page_height_mm(content)),
            QPageSize.Unit.Millimeter,
        )
    )
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
    """Imprime un documento térmico (presupuesto, ticket de venta) respetando el
    rol de la PC: el Servidor de impresión lo imprime local (con preview); una
    Estación lo encola para que lo imprima el servidor. Así las estaciones nunca
    tocan una impresora.
    """
    from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

    route_tickets(parent, title, [content])


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
