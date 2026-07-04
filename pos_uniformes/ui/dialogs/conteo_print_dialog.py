"""Diálogo para previsualizar e imprimir hojas de conteo.

Delegación directa a open_tickets_print_dialog: un solo diálogo con todas
las hojas, cada una como print job separado (autocut entre hojas) mediante
TicketPrintQueue — segura ante el cierre del diálogo a media cola.

Antes tenía su propia cola con QTimer sin guard: cerrar el diálogo mientras
imprimía tocaba el botón destruido (WA_DeleteOnClose) → RuntimeError en slot
→ qFatal → se cerraba el POS completo.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from pos_uniformes.ui.dialogs.printable_text_dialog import open_tickets_print_dialog


def open_conteo_print_dialog(
    parent: QWidget,
    title: str,
    sheets: list[str],
) -> None:
    """Abre diálogo con preview de todas las hojas y botón para imprimir."""
    open_tickets_print_dialog(parent, title, sheets, unit_label="hoja")
