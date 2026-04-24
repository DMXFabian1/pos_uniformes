"""Tono semáforo de stock reutilizable en tablas y vistas."""

from __future__ import annotations

_LOW_STOCK_THRESHOLD = 3


def resolve_stock_tone(stock: int, *, stock_minimo: int | None = None) -> str:
    """danger=0, warning=bajo/bajo_minimo, positive=saludable."""
    if stock == 0:
        return "danger"
    below_min = stock_minimo is not None and stock < stock_minimo
    if stock <= _LOW_STOCK_THRESHOLD or below_min:
        return "warning"
    return "positive"


def resolve_row_tone_from_stock(stock: int) -> str | None:
    """Tono de fila basado solo en stock: danger/warning/None."""
    if stock == 0:
        return "danger"
    if stock <= _LOW_STOCK_THRESHOLD:
        return "warning"
    return None
