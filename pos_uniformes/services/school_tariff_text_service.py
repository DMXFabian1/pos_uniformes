"""Builder de texto para tarifarios de escuela (ticket térmico 80 mm)."""

from __future__ import annotations

import textwrap
from decimal import Decimal

from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
    TICKET_CHAR_WIDTH as _W,
    tk_bot,
    tk_center,
    tk_dbl,
    tk_fmt,
    tk_line,
    tk_mid,
    tk_row,
    tk_top,
)

_IW = _W - 4  # ancho interno


def build_school_tariff_text(
    *,
    tariff: dict,
    business_name: str = "MAXIMODA",
    business_phone: str = "",
) -> str:
    """Genera el texto del tarifario listo para ticket térmico."""
    escuela = tariff.get("escuela_nombre", "")
    productos = tariff.get("productos", [])

    lines: list[str] = []

    # — Encabezado —
    lines.append(business_name.center(_W))
    if business_phone:
        lines.append(f"Tel: {business_phone}".center(_W))
    lines.append("Lista de precios".center(_W))

    # — Escuela —
    lines.append(tk_top())
    lines.append(tk_center(escuela[:_IW]))
    lines.append(tk_dbl())

    # — Productos —
    first = True
    for prod in productos:
        nombre = prod.get("nombre", "")
        tallas = prod.get("tallas", [])
        if not tallas:
            continue

        if not first:
            lines.append(tk_mid())
        first = False

        # Nombre del producto
        for dl in textwrap.wrap(str(nombre), width=_IW) or [str(nombre)]:
            lines.append(tk_line(dl))

        # Agrupar tallas por precio
        price_groups = _group_tallas_by_price(tallas)
        for precio, group_tallas in price_groups:
            tallas_str = ", ".join(group_tallas)
            price_str = f"${tk_fmt(precio)}"
            label = f"  {tallas_str}"
            if len(label) + 1 + len(price_str) <= _IW:
                lines.append(tk_row(label, price_str))
            else:
                # Partir tallas en varias líneas si no caben
                for chunk in textwrap.wrap(label, width=_IW):
                    lines.append(tk_line(chunk))
                lines.append(tk_line(price_str.rjust(_IW)))

    lines.append(tk_bot())

    # — Pie —
    lines.append("")
    lines.append("Precios sujetos a cambio".center(_W))
    lines.append("sin previo aviso.".center(_W))

    return "\n".join(lines)


def _group_tallas_by_price(tallas: list[dict]) -> list[tuple[Decimal, list[str]]]:
    """Agrupa tallas consecutivas que compartan el mismo precio."""
    groups: list[tuple[Decimal, list[str]]] = []
    for t in tallas:
        precio = Decimal(str(t["precio"]))
        talla = str(t["talla"])
        if groups and groups[-1][0] == precio:
            groups[-1][1].append(talla)
        else:
            groups.append((precio, [talla]))
    return groups
