"""Dialogo reutilizable para mostrar e imprimir tickets de 80 mm.

- open_printable_text_dialog: un solo documento (presupuestos, etc.).
- open_tickets_print_dialog : uno o varios tickets; un solo "Imprimir" los
  manda todos como jobs separados (autocut entre cada uno).

Ambos comparten la misma cola segura (TicketPrintQueue): si se cierra el
dialogo mientras hay un QTimer pendiente, no se tocan widgets ya destruidos.
"""

from __future__ import annotations

import logging

from collections.abc import Callable

from PyQt6.QtCore import QSizeF, Qt, QTimer
from PyQt6.QtGui import QFontDatabase, QImage, QPageLayout, QPainter, QPageSize
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
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
from pos_uniformes.ui.helpers.scanner_enter_guard import ScannerEnterGuard
from pos_uniformes.ui.helpers.ticket_print_queue import TicketPrintQueue

# Avance extra (mm) después del contenido para que la cuchilla del autocutter
# —que corta ~10 mm por encima del cabezal— no recorte la última línea. Con la
# página de alto dinámico, este es el único "colchón" de papel entre el fin del
# ticket y el corte, en vez de los 600 mm fijos de antes que cortaban a destiempo.
TICKET_BOTTOM_FEED_MM = 12.0
# Alto de página histórico de los TICKETS (venta/apartado/presupuesto). No se
# toca: el driver escala el render según el tamaño de página, así que cambiarlo
# altera su fuente y espaciado. Solo las hojas de conteo usan alto dinámico.
_LEGACY_PAGE_HEIGHT_MM = 600.0
# DPI de referencia para medir el alto del texto (ScreenResolution ≈ 96 dpi). El
# alto físico en mm es independiente del dpi (la fuente está en puntos), así que
# medir a 96 dpi coincide con lo que dibuja drawText en la impresora.
_MEASURE_DPI = 96


logger = logging.getLogger(__name__)


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


_printer_warmed_up = False


def _warm_up_printer_once() -> None:
    """Consume el PRIMER trabajo de impresión de la sesión con una página mínima.

    El driver de la térmica aplica el tamaño de página custom recién desde el
    SEGUNDO trabajo; el primero sale con el tamaño por defecto (más ancho) y se
    recorta por la derecha (lo centrado se corre y el borde derecho se pierde).
    Este calentamiento (una sola vez por proceso, página casi vacía) absorbe ese
    primer trabajo defectuoso para que TODAS las hojas reales salgan con su
    tamaño correcto. Nunca rompe la impresión si falla.
    """
    global _printer_warmed_up
    if _printer_warmed_up:
        return
    _printer_warmed_up = True
    try:
        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        ticket_printer, _ = _load_print_preferences()
        if ticket_printer:
            printer.setPrinterName(ticket_printer)
        printer.setPageSize(
            QPageSize(QSizeF(TICKET_PAPER_WIDTH_MM, 6.0), QPageSize.Unit.Millimeter)
        )
        printer.setFullPage(True)
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        painter = QPainter()
        if painter.begin(printer):
            painter.end()  # página en blanco mínima
    except Exception:  # noqa: BLE001 — el calentamiento nunca debe romper la impresión
        pass


def _try_print_escpos(printer_name: str, content: str, copies: int) -> bool:
    """Intenta imprimir por ESC/POS crudo (Windows: pywin32; Mac/Linux: CUPS).

    False si no hay impresora, está apagado, o el envío falla → cae a QPrinter.
    """
    if not printer_name:
        return False
    try:
        from pos_uniformes.services.escpos_settings_cache_service import (
            load_escpos_settings,
        )

        if not load_escpos_settings().enabled:
            return False
        from pos_uniformes.ui.helpers.escpos_ticket_print_helper import (
            print_ticket_escpos,
        )

        return print_ticket_escpos(printer_name, content, copies=copies)
    except Exception:  # noqa: BLE001 — cae al camino QPrinter
        return False


def _sin_marcadores(content: str) -> str:
    """Quita el marcador del dibujo de temporada, poniendo el de ASCII.

    Este camino dibuja TEXTO: no sabe imprimir puntos. Sin esto saldría el
    literal «[[IMG:halloween]]» en el papel, que es peor que no poner nada.
    """
    try:
        from pos_uniformes.services.temporada_service import sin_marcadores

        return sin_marcadores(content)
    except Exception:  # noqa: BLE001 — el ticket se imprime igual
        return content


def _render_drawtext(printer: QPrinter, content: str) -> bool:
    """Dibuja el texto en la página con la fuente/flags de siempre.

    Si el contenido trae el marcador del dibujo de temporada, se parte en
    bloques y la imagen se dibuja entre ellos. Esto es lo que hace que el dibujo
    salga en PNG **en los tickets**: los tickets NO pasan por ESC/POS —ese
    camino es solo de las hojas de conteo— así que el raster del otro lado no
    les servía de nada.

    Si algo del dibujo falla, se cae a pintar todo el texto de una, con el
    marcador cambiado por el dibujo de caracteres: exactamente lo de siempre.
    """
    bloques = _bloques_con_imagen(content)
    painter = QPainter()
    if not painter.begin(printer):
        return False
    try:
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(TICKET_FONT_POINT_SIZE)
        font.setBold(True)
        painter.setFont(font)
        rect = painter.viewport()
        banderas = (
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        )
        if bloques is None:
            painter.drawText(rect, banderas, _sin_marcadores(content))
            return True

        y = rect.top()
        for clase, valor in bloques:
            if clase == "texto":
                alto = painter.boundingRect(
                    rect.adjusted(0, y - rect.top(), 0, 0), banderas, valor
                ).height()
                painter.drawText(
                    rect.adjusted(0, y - rect.top(), 0, 0), banderas, valor
                )
                y += alto
            else:
                y += _dibujar_imagen(painter, rect, y, valor)
    finally:
        painter.end()
    return True


def _bloques_con_imagen(content: str):
    """[(clase, valor)] partiendo el contenido en el marcador. None si no hay.

    `None` quiere decir «no hay nada que dibujar»: así el camino de siempre se
    queda tal cual, sin pagar ni un cálculo de más.
    """
    try:
        from pos_uniformes.services.temporada_service import (
            MARCADOR_FIN,
            MARCADOR_INICIO,
            imagen_para_marcador,
            partir_marcador,
        )
    except Exception:  # noqa: BLE001
        return None
    if not content or MARCADOR_INICIO not in content:
        return None

    bloques = []
    for i, parte in enumerate(content.split(MARCADOR_INICIO)):
        if i == 0:
            bloques.append(("texto", parte))
            continue
        cuerpo, _, resto = parte.partition(MARCADOR_FIN)
        nombre, respaldo = partir_marcador(cuerpo)
        if respaldo:
            # Un marcador con respaldo trae escrito cómo decirse sin dibujo, y
            # por aquí eso es lo que conviene: Qt arma la página a 302 puntos y
            # el driver la vuelve a estirar a 576, así que un dibujo fino sale
            # apolillado. El logo escrito se lee; el logo apolillado, no.
            return None
        ruta = imagen_para_marcador(nombre)
        if ruta is None:
            # Sin PNG, el renglón se va: el llamador ya puso el de ASCII.
            return None
        bloques.append(("imagen", str(ruta)))
        bloques.append(("texto", resto))
    return bloques


def _dibujar_imagen(painter: QPainter, rect, y: int, ruta: str) -> int:
    """Dibuja el PNG centrado y devuelve cuánto alto ocupó.

    El ancho se limita a la mitad del papel para que el dibujo no compita con el
    total, y se escala con `KeepAspectRatio` para no deformarlo.
    """
    from PyQt6.QtCore import Qt as _Qt
    from PyQt6.QtGui import QImage

    imagen = QImage(ruta)
    if imagen.isNull():
        return 0
    ancho = max(1, rect.width() // 2)
    escalada = imagen.scaledToWidth(ancho, _Qt.TransformationMode.SmoothTransformation)
    x = rect.left() + (rect.width() - escalada.width()) // 2
    painter.drawImage(x, y, escalada)
    return escalada.height()


def _ticket_como_imagen_activo() -> bool:
    """¿Esta máquina imprime el ticket dibujado? Ante la duda, no."""
    try:
        from pos_uniformes.services.escpos_settings_cache_service import (
            load_escpos_settings,
        )

        s = load_escpos_settings()
        return bool(s.enabled and s.ticket_como_imagen)
    except Exception:  # noqa: BLE001
        return False


def _print_ticket_job(content: str) -> bool:
    """Tickets de venta / apartado / presupuesto: camino HISTÓRICO, intacto.

    Página FIJA de 600 mm + drawText, exactamente como siempre. No se le aplica
    alto dinámico ni ESC/POS a propósito: el driver escala el render según el
    tamaño de página, así que cambiarlo altera la fuente y el espaciado del
    ticket. El alto dinámico y ESC/POS son SOLO para las hojas de conteo
    (ver `_print_conteo_job`), que es donde había problema de corte.
    """
    ticket_printer, copies = _load_print_preferences()

    # Camino nuevo: el ticket DIBUJADO, mandado como puntos. Se enciende por
    # máquina y apagado se comporta exactamente como siempre. Si falla por lo
    # que sea, se cae al camino de abajo: un ticket tiene que salir.
    if _ticket_como_imagen_activo():
        try:
            from pos_uniformes.ui.helpers.escpos_ticket_print_helper import (
                print_ticket_imagen_escpos,
            )

            if print_ticket_imagen_escpos(ticket_printer, content, copies=copies):
                return True
        except Exception:  # noqa: BLE001
            logger.exception("Ticket dibujado: no se pudo, va por el camino de siempre")

    printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
    if ticket_printer:
        printer.setPrinterName(ticket_printer)
    printer.setCopyCount(copies)
    printer.setPageSize(
        QPageSize(
            QSizeF(TICKET_PAPER_WIDTH_MM, _LEGACY_PAGE_HEIGHT_MM),
            QPageSize.Unit.Millimeter,
        )
    )
    printer.setFullPage(True)
    printer.setPageOrientation(QPageLayout.Orientation.Portrait)
    return _render_drawtext(printer, content)


def _print_conteo_job(content: str) -> bool:
    """Hojas de conteo: ESC/POS crudo si aplica; si no, página de alto dinámico.

    Solo para conteos. En Windows/Mac con ESC/POS habilitado manda los bytes al
    spooler RAW (sin driver → corte exacto). Si no, cae al QPrinter con la página
    del alto del contenido (que arregló el corte de las hojas).
    """
    ticket_printer, copies = _load_print_preferences()

    if _try_print_escpos(ticket_printer, content, copies):
        return True

    # El primer trabajo de la sesión sale con el tamaño por defecto del driver;
    # se calienta una vez para que la primera hoja real ya salga bien.
    _warm_up_printer_once()

    printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
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
    return _render_drawtext(printer, content)


# Nombres públicos para el despachador del satélite. OJO: son distintos a
# propósito — los tickets conservan su estética histórica y los conteos usan el
# camino nuevo (alto dinámico / ESC/POS).
print_ticket_text = _print_ticket_job
print_conteo_sheet = _print_conteo_job


_RE_TOTAL_LINEA = None


def total_del_ticket(content: str) -> str | None:
    """Saca el total de un ticket ("TOTAL A PAGAR: $285.00", "TOTAL: $617.00")
    para mostrarlo grande en el diálogo. Ignora "Subtotal". None si no hay."""
    global _RE_TOTAL_LINEA
    if _RE_TOTAL_LINEA is None:
        import re

        _RE_TOTAL_LINEA = re.compile(
            r"^\s*TOTAL(?:\s+A\s+PAGAR)?\s*:\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*$",
            re.IGNORECASE,
        )
    for raw in (content or "").splitlines():
        linea = raw.replace("│", " ").replace("|", " ").strip()
        match = _RE_TOTAL_LINEA.match(linea)
        if match:
            return f"${match.group(1)}"
    return None


def pintar_previa(editor: QTextEdit, content: str) -> None:
    """Pone en la previa EXACTAMENTE lo que va a salir del papel.

    Con el ticket dibujado encendido, la previa enseña la misma imagen que se
    manda a la impresora. Antes seguía enseñando el texto: previa y papel
    decían cosas distintas, y una previa que no se parece al papel no sirve
    para lo que sirve una previa (Daniel, 2026-10-07).
    """
    if _ticket_como_imagen_activo():
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QTextDocument

            from pos_uniformes.services.ticket_imagen_service import render_ticket

            imagen = render_ticket(content)
            editor.document().addResource(
                QTextDocument.ResourceType.ImageResource, QUrl("ticket://previa"), imagen
            )
            editor.setHtml(
                '<div align="center"><img src="ticket://previa" '
                f'width="{imagen.width()}"></div>'
            )
            return
        except Exception:  # noqa: BLE001 — sin dibujo, la previa de siempre
            logger.exception("Previa dibujada: no se pudo, va la de texto")
    editor.setPlainText(_sin_marcadores(content))


def _build_ticket_editor(content: str) -> QTextEdit:
    editor = QTextEdit()
    editor.setReadOnly(True)
    mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
    editor.setStyleSheet(
        f'QTextEdit {{ font-family: "{mono_family}"; font-size: {TICKET_FONT_POINT_SIZE}pt;'
        f" font-weight: bold; }}"
    )
    pintar_previa(editor, content)
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
    print_fn: "Callable[[str], bool] | None" = None,
    alt_tickets: list[str] | None = None,
    alt_checkbox_label: str | None = None,
    on_printed: "Callable[[], None] | None" = None,
    on_back: "Callable[[], None] | None" = None,
) -> None:
    """Muestra uno o varios tickets en una sola vista.

    on_back agrega "← Regresar": cierra sin imprimir (no llama on_printed) y
    después invoca on_back para volver a la pregunta anterior (p.ej. cambiar
    copia / forma de pago / sin ticket en venta rápida).

    Un solo clic en "Imprimir" manda todos los tickets como jobs separados
    (cada uno se corta por el autocutter). Reemplaza el flujo anterior de un
    dialogo por copia, que obligaba a imprimir dos veces.

    unit_label permite reutilizar el dialogo para otros documentos del mismo
    formato (p.ej. "hoja" para las hojas de conteo).

    print_fn permite elegir el camino de impresión: por defecto el de TICKETS
    (estética histórica); las hojas de conteo pasan `print_conteo_sheet`.

    alt_tickets + alt_checkbox_label agregan un checkbox (desmarcado): al
    marcarlo se imprime/previsualiza el juego alterno en lugar del base
    (p.ej. copia interna con la comisión de la terminal descontada).

    on_printed se invoca UNA vez, cuando la impresión realmente arranca
    (clic en Imprimir) — para efectos que solo deben ocurrir si se imprimió,
    como registrar la venta en la Libreta. Cerrar sin imprimir no lo llama.
    """
    tickets = [t for t in tickets if t and t.strip()]
    if not tickets:
        return
    alt_tickets = [t for t in (alt_tickets or []) if t and t.strip()]

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    # Pensado para pantalla táctil: botones grandes abajo, vista previa
    # limpia en medio, nada pequeño que atinarle con el dedo.
    dialog.resize(660, 680)
    dialog.setStyleSheet(
        "QDialog { background: #f4ede2; }"
        "QLabel { color: #2c2a27; background: transparent; }"
        "QTextEdit { background: #ffffff; color: #2c2a27;"
        "  border: 1px solid #ddd0c0; border-radius: 12px; padding: 14px; }"
        "QCheckBox { color: #2c2a27; font-size: 15px; font-weight: 600;"
        "  padding: 10px 4px; spacing: 10px; }"
        "QCheckBox::indicator { width: 26px; height: 26px; }"
        "QPushButton#ticketCerrar { background: #f8f2e9; color: #73341c;"
        "  border: 1px solid #ddd0c0; border-radius: 14px;"
        "  font-size: 16px; font-weight: 700; min-height: 56px; padding: 0 28px; }"
        "QPushButton#ticketCerrar:pressed { background: #e8dbc7; }"
        "QPushButton#ticketImprimir { background: #a84f2d; color: #ffffff;"
        "  border: none; border-radius: 14px;"
        "  font-size: 18px; font-weight: 800; min-height: 56px; padding: 0 28px; }"
        "QPushButton#ticketImprimir:pressed { background: #8a4326; }"
        "QPushButton#ticketImprimir:disabled { background: #c9a996; color: #f4ede2; }"
    )
    ScannerEnterGuard(dialog)

    layout = QVBoxLayout()
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(12)

    n = len(tickets)
    titulo = QLabel(title)
    titulo.setStyleSheet("font-size: 19px; font-weight: 800; color: #73341c;")
    subtitulo = QLabel(
        f"Para imprimir: 1 {unit_label}"
        if n == 1
        else f"Para imprimir: {n} {unit_label}s — salen en un solo toque"
    )
    subtitulo.setStyleSheet("font-size: 13px; color: #5f594f;")
    encabezado = QHBoxLayout()
    encabezado.setSpacing(12)
    textos_ly = QVBoxLayout()
    textos_ly.setSpacing(2)
    textos_ly.addWidget(titulo)
    textos_ly.addWidget(subtitulo)
    encabezado.addLayout(textos_ly, 1)
    # Recuadro con el TOTAL arriba a la derecha (pedido de Daniel
    # 2026-09-07): la cajera lo ve sin leer el ticket. Sale del primer
    # ticket (el del cliente); si el documento no trae total, no aparece.
    total_txt = total_del_ticket(tickets[0])
    if total_txt:
        total_box = QLabel(f"Total\n{total_txt}")
        total_box.setObjectName("ticketTotal")
        total_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_box.setStyleSheet(
            "QLabel#ticketTotal { background: #a84f2d; color: #ffffff;"
            "  border-radius: 14px; padding: 8px 22px;"
            "  font-size: 26px; font-weight: 900; }"
        )
        encabezado.addWidget(total_box, 0, Qt.AlignmentFlag.AlignTop)
    layout.addLayout(encabezado)

    editor = _build_ticket_editor("\n\n".join(tickets))

    idle_label = "🖨  Imprimir" if n == 1 else f"🖨  Imprimir {n} {unit_label}s"
    print_button = QPushButton(idle_label)
    print_button.setObjectName("ticketImprimir")
    print_button.setAutoDefault(False)
    close_button = QPushButton("Cerrar")
    close_button.setObjectName("ticketCerrar")
    close_button.setAutoDefault(False)

    def _set_status(text: str) -> None:
        print_button.setText(text)
        print_button.setEnabled(text == idle_label)

    def _make_queue(queue_tickets: list[str]) -> TicketPrintQueue:
        total = len(queue_tickets)

        def _report(ok: int, errors: int) -> None:
            if not errors:
                return
            if ok == 0:
                msg = "No se pudo imprimir.\nVerifica que la impresora este conectada."
            else:
                msg = f"Se imprimieron {ok} de {total} {unit_label}s.\n{errors} fallaron."
            QMessageBox.warning(dialog, "Error de impresion", msg)

        return TicketPrintQueue(
            queue_tickets,
            print_fn=print_fn or _print_ticket_job,
            schedule=QTimer.singleShot,
            on_status=_set_status,
            on_done=_report,
            idle_label=idle_label,
        )

    queue = _make_queue(tickets)
    alt_queue = _make_queue(alt_tickets) if alt_tickets else None

    alt_checkbox: QCheckBox | None = None
    if alt_queue is not None and alt_checkbox_label:
        alt_checkbox = QCheckBox(alt_checkbox_label)
        alt_checkbox.setChecked(False)
        alt_checkbox.toggled.connect(
            lambda checked: pintar_previa(
                editor, "\n\n".join(alt_tickets if checked else tickets)
            )
        )

    printed_notified = False

    def _start_print() -> None:
        nonlocal printed_notified
        # Candado entre AMBAS colas: un segundo clic con el checkbox cambiado
        # arrancaba la otra cola en paralelo (tickets duplicados intercalados).
        if queue.is_printing() or (alt_queue is not None and alt_queue.is_printing()):
            return
        use_alt = alt_checkbox is not None and alt_checkbox.isChecked()
        (alt_queue if use_alt else queue).start()
        if on_printed is not None and not printed_notified:
            printed_notified = True
            try:
                on_printed()
            except Exception:  # noqa: BLE001 — el efecto no debe romper la impresión
                pass

    print_button.clicked.connect(_start_print)
    close_button.clicked.connect(dialog.reject)
    volver = {"si": False}
    back_button = None
    if on_back is not None:
        back_button = QPushButton("←  Regresar")
        back_button.setObjectName("ticketCerrar")  # mismo estilo suave que Cerrar
        back_button.setAutoDefault(False)

        def _regresar() -> None:
            if queue.is_printing() or (alt_queue is not None and alt_queue.is_printing()):
                return
            volver["si"] = True
            dialog.reject()

        back_button.clicked.connect(_regresar)
    # Al cerrar el dialogo, la cola deja de tocar sus widgets (evita crash).
    def _close_queues(_result: int) -> None:
        queue.close()
        if alt_queue is not None:
            alt_queue.close()

    dialog.finished.connect(_close_queues)

    layout.addWidget(editor, 1)
    if alt_checkbox is not None:
        layout.addWidget(alt_checkbox)
    botones_ly = QHBoxLayout()
    botones_ly.setSpacing(12)
    if back_button is not None:
        botones_ly.addWidget(back_button, 1)
    botones_ly.addWidget(close_button, 1)
    botones_ly.addWidget(print_button, 2)  # el botón principal, bien grande
    layout.addLayout(botones_ly)
    dialog.setLayout(layout)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dialog.exec()
    if volver["si"] and on_back is not None:
        on_back()
