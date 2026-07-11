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
    """Abre diálogo con preview de todas las hojas y botón para imprimir.

    Si esta máquina está en modo satélite, encola las hojas para el satélite en
    vez de abrir el diálogo de impresión local.
    """
    from pos_uniformes.ui.helpers.conteo_routing_helper import (
        maybe_route_conteo_to_satellite,
    )

    if maybe_route_conteo_to_satellite(sheets, titulo=title, parent=parent):
        return
    open_tickets_print_dialog(parent, title, sheets, unit_label="hoja")
