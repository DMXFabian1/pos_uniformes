"""Helpers para formatear tickets termicos de 80 mm."""

from __future__ import annotations

import textwrap

from PyQt6.QtGui import QFont, QFontDatabase, QTextDocument

TICKET_PAPER_WIDTH_MM = 80.0
TICKET_HORIZONTAL_MARGIN_MM = 2.0
TICKET_TEXT_WIDTH_MM = TICKET_PAPER_WIDTH_MM - (TICKET_HORIZONTAL_MARGIN_MM * 2)
TICKET_FONT_POINT_SIZE = 8

# ── Box-drawing helpers para tickets de 38 columnas ──────────────

TICKET_CHAR_WIDTH = 38
_IW = TICKET_CHAR_WIDTH - 4  # ancho interno sin "│ " y " │"


def tk_top() -> str:
    return "┌" + "─" * (TICKET_CHAR_WIDTH - 2) + "┐"


def tk_mid() -> str:
    return "├" + "─" * (TICKET_CHAR_WIDTH - 2) + "┤"


def tk_bot() -> str:
    return "└" + "─" * (TICKET_CHAR_WIDTH - 2) + "┘"


def tk_dbl() -> str:
    return "╞" + "═" * (TICKET_CHAR_WIDTH - 2) + "╡"


def tk_line(text: str) -> str:
    return f"│ {text:<{_IW}} │"


def tk_center(text: str) -> str:
    return f"│ {text:^{_IW}} │"


def tk_row(label: str, value: str) -> str:
    gap = _IW - len(label) - len(value)
    inner = f"{label}{' ' * max(1, gap)}{value}"
    return f"│ {inner:<{_IW}} │"


def tk_field(label: str, value: str, lines: list[str]) -> None:
    """Agrega un campo label: value al ticket, con wrap si es necesario."""
    if len(label + value) + 1 > _IW:
        lines.append(tk_line(label))
        for part in textwrap.wrap(value, width=_IW):
            lines.append(tk_line(part))
    else:
        lines.append(tk_row(label, value))


def tk_product_price(meta: str, value: str, lines: list[str]) -> None:
    """Agrega linea de precio, partiendo en dos si no cabe."""
    if len(meta) + 1 + len(value) > _IW:
        lines.append(tk_line(meta))
        lines.append(tk_line(value.rjust(_IW)))
    else:
        lines.append(tk_row(meta, value))


def tk_fmt(value: object) -> str:
    try:
        from decimal import Decimal
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except Exception:
        return str(value)


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
