"""Helpers para formatear tickets termicos de 80 mm."""

from __future__ import annotations

from PyQt6.QtGui import QFont, QFontDatabase, QTextDocument

TICKET_PAPER_WIDTH_MM = 80.0
TICKET_HORIZONTAL_MARGIN_MM = 2.0
TICKET_TEXT_WIDTH_MM = TICKET_PAPER_WIDTH_MM - (TICKET_HORIZONTAL_MARGIN_MM * 2)
TICKET_FONT_POINT_SIZE = 8


def millimeters_to_points(value_mm: float) -> float:
    """Convierte milimetros a puntos tipograficos."""
    return (value_mm / 25.4) * 72.0


def build_ticket_document(content: str, *, text_width_mm: float | None = None) -> QTextDocument:
    """Prepara un documento de texto optimizado para ticket termico de 80 mm."""
    effective_width = text_width_mm if text_width_mm is not None else TICKET_TEXT_WIDTH_MM
    document = QTextDocument()
    document.setPlainText(content)
    document.setDocumentMargin(millimeters_to_points(TICKET_HORIZONTAL_MARGIN_MM))
    document.setTextWidth(millimeters_to_points(effective_width))

    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setStyleHint(QFont.StyleHint.TypeWriter)
    font.setPointSize(TICKET_FONT_POINT_SIZE)
    font.setBold(True)
    document.setDefaultFont(font)
    return document


def build_ticket_print_font() -> QFont:
    """Fuente negrita para imprimir el ticket via QPainter."""
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setStyleHint(QFont.StyleHint.TypeWriter)
    font.setPointSize(TICKET_FONT_POINT_SIZE)
    font.setBold(True)
    return font
