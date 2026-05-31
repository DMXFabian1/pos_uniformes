"""Genera hojas de pedido para impresora térmica de 80mm.

Recibe una lista de items seleccionados desde la pestaña Disponibilidad
y genera hojas agrupadas por producto, con stock actual y espacio para
escribir la cantidad a pedir.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime

# ── Box-drawing (38 cols, 80mm thermal) ─────────────────────────────────────
# Reutilizamos las mismas dimensiones que conteo_sheet_service.

_W = 38
_IW = _W - 4


def _top() -> str:
    return "┌" + "─" * (_W - 2) + "┐"


def _mid() -> str:
    return "├" + "─" * (_W - 2) + "┤"


def _bot() -> str:
    return "└" + "─" * (_W - 2) + "┘"


def _line(text: str) -> str:
    return f"│ {text:<{_IW}} │"


def _center(text: str) -> str:
    return f"│ {text:^{_IW}} │"


def _row3(c1: str, c2: str, c3: str, widths: tuple[int, int, int]) -> str:
    w1, w2, w3 = widths
    inner = f"{c1:<{w1}}{c2:^{w2}}{c3:^{w3}}"
    return f"│ {inner:<{_IW}} │"


# ── Ordenamiento de tallas ──────────────────────────────────────────────────

_LETRA_ORDER = {
    "CH": 0, "MD": 1, "GD": 2, "EXG": 3,
    "XXS": 4, "XS": 5, "S": 6, "M": 7, "L": 8, "XL": 9, "XXL": 10,
}


def _talla_sort_key(talla: str):
    t = talla.strip().upper()
    if len(t) > 2 and t[:-2].isdigit():
        return (0, int(t[:-2]), t)
    try:
        return (1, int(t), "")
    except ValueError:
        pass
    return (2, _LETRA_ORDER.get(t, 99), t)


# ── Builder ─────────────────────────────────────────────────────────────────

def build_pedido_sheets(items: list[dict]) -> list[str]:
    """Genera hojas de pedido agrupadas por producto.

    Cada item es un dict con: producto, talla, stock_tienda, stock_bodega, stock_piso.
    Retorna lista de strings listos para imprimir en térmica.
    """
    if not items:
        return []

    import textwrap

    # Agrupar por escuela → producto → tallas
    escuelas: OrderedDict[str, OrderedDict[str, list[dict]]] = OrderedDict()
    for item in items:
        escuela = item.get("escuela", "Sin escuela")
        nombre = item.get("producto", "Sin nombre")
        if escuela not in escuelas:
            escuelas[escuela] = OrderedDict()
        if nombre not in escuelas[escuela]:
            escuelas[escuela][nombre] = []
        escuelas[escuela][nombre].append(item)

    # Ordenar escuelas alfabéticamente y tallas dentro de cada grupo
    escuelas_sorted = OrderedDict(sorted(escuelas.items(), key=lambda x: x[0]))
    for productos in escuelas_sorted.values():
        for tallas in productos.values():
            tallas.sort(key=lambda x: _talla_sort_key(x.get("talla", "")))

    fecha_str = datetime.now().strftime("%d/%m/%Y")
    sheets: list[str] = []

    for escuela, productos in escuelas_sorted.items():
        n_hojas = len(productos)
        for idx, (producto, tallas) in enumerate(productos.items(), start=1):
            lines: list[str] = []
            lines.append(_top())
            lines.append(_center(f"PEDIDO {idx}/{n_hojas}"))
            lines.append(_mid())

            lines.append(_line(f"Escuela: {escuela}"))
            lines.append(_line(f"Fecha:   {fecha_str}"))
            lines.append(_mid())

            for part in textwrap.wrap(producto, width=_IW):
                lines.append(_center(part))

            lines.append(_mid())

            col_widths = (14, 10, 10)
            lines.append(_row3("Talla", "Stock", "Pedir", col_widths))
            lines.append(_mid())

            for t in tallas:
                talla = t.get("talla", "U")
                stock = t.get("stock_tienda", 0)
                lines.append(_row3(talla, str(stock), "____", col_widths))

            lines.append(_bot())

            lines.append("")
            lines.append(f"  Pidió: {'_' * 24}")
            lines.append("")
            lines.append("")

            sheets.append("\n".join(lines))

    return sheets


def build_pedido_texto(items: list[dict]) -> str:
    """Genera resumen de pedido como texto plano (para copiar/pegar en WhatsApp, etc.)."""
    if not items:
        return ""

    fecha_str = datetime.now().strftime("%d/%m/%Y")

    # Agrupar por escuela → producto → tallas
    escuelas: OrderedDict[str, OrderedDict[str, list[dict]]] = OrderedDict()
    for item in items:
        escuela = item.get("escuela", "Sin escuela")
        nombre = item.get("producto", "Sin nombre")
        if escuela not in escuelas:
            escuelas[escuela] = OrderedDict()
        if nombre not in escuelas[escuela]:
            escuelas[escuela][nombre] = []
        escuelas[escuela][nombre].append(item)

    escuelas_sorted = OrderedDict(sorted(escuelas.items(), key=lambda x: x[0]))
    for productos in escuelas_sorted.values():
        for tallas in productos.values():
            tallas.sort(key=lambda x: _talla_sort_key(x.get("talla", "")))

    lines = [f"📋 PEDIDO — {fecha_str}", ""]

    for escuela, productos in escuelas_sorted.items():
        lines.append(f"🏫 {escuela}")
        for producto, tallas in productos.items():
            parts = []
            for t in tallas:
                talla = t.get("talla", "U")
                stock = t.get("stock_tienda", 0)
                parts.append(f"{talla} ({stock})")
            lines.append(f"• {producto}: {', '.join(parts)}")
        lines.append("")

    return "\n".join(lines).rstrip()
