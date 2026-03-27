"""Helpers para formatear tickets termicos de 58 mm."""

from __future__ import annotations

from PyQt6.QtGui import QFont, QFontDatabase, QTextDocument

TICKET_PAPER_WIDTH_MM = 58.0
TICKET_HORIZONTAL_MARGIN_MM = 2.0
TICKET_TEXT_WIDTH_MM = TICKET_PAPER_WIDTH_MM - (TICKET_HORIZONTAL_MARGIN_MM * 2)
TICKET_FONT_POINT_SIZE = 8


def millimeters_to_points(value_mm: float) -> float:
    """Convierte milimetros a puntos tipograficos."""
    return (value_mm / 25.4) * 72.0


def build_ticket_document(content: str) -> QTextDocument:
    """Prepara un documento de texto optimizado para ticket termico de 58 mm."""
    document = QTextDocument()
    document.setPlainText(content)
    document.setDocumentMargin(millimeters_to_points(TICKET_HORIZONTAL_MARGIN_MM))
    document.setTextWidth(millimeters_to_points(TICKET_TEXT_WIDTH_MM))

    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setStyleHint(QFont.StyleHint.TypeWriter)
    font.setPointSize(TICKET_FONT_POINT_SIZE)
    document.setDefaultFont(font)
    return document
