"""Helpers para formatear tickets termicos de 80 mm."""

from __future__ import annotations

from PyQt6.QtGui import QFont, QTextDocument

TICKET_PAPER_WIDTH_MM = 80.0
TICKET_HORIZONTAL_MARGIN_MM = 2.0
TICKET_TEXT_WIDTH_MM = TICKET_PAPER_WIDTH_MM - (TICKET_HORIZONTAL_MARGIN_MM * 2)
TICKET_FONT_POINT_SIZE = 8


def millimeters_to_points(value_mm: float) -> float:
    """Convierte milimetros a puntos tipograficos."""
    return (value_mm / 25.4) * 72.0


def build_ticket_document(content: str, *, text_width_mm: float | None = None) -> QTextDocument:
    """Prepara un documento HTML optimizado para ticket termico de 80 mm.

    text_width_mm: ancho de texto en mm. Si se omite usa TICKET_TEXT_WIDTH_MM (fallback para preview).
    Al imprimir, pasar el ancho real del area imprimible del driver para ocupar todo el papel.
    """
    effective_width = text_width_mm if text_width_mm is not None else TICKET_TEXT_WIDTH_MM
    document = QTextDocument()
    document.setHtml(content)
    document.setDocumentMargin(millimeters_to_points(TICKET_HORIZONTAL_MARGIN_MM))
    document.setTextWidth(millimeters_to_points(effective_width))

    font = QFont("Arial")
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setPointSize(TICKET_FONT_POINT_SIZE)
    document.setDefaultFont(font)
    return document
