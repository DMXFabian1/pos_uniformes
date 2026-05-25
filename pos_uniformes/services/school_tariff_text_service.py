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


# Valores de género que siempre se incluyen sin importar el filtro
_GENEROS_UNISEX = {"", "UNISEX", "ADULTO", "MIXTO"}

# Equivalencias: Niña↔Mujer, Niño↔Hombre (un producto con genero="Mujer"
# aparece cuando el filtro es "NIÑA" y viceversa)
_GENERO_EQUIV: dict[str, set[str]] = {
    "NIÑA": {"NIÑA", "MUJER"},
    "NIÑO": {"NIÑO", "HOMBRE"},
    "MUJER": {"MUJER", "NIÑA"},
    "HOMBRE": {"HOMBRE", "NIÑO"},
}


def build_school_tariff_text(
    *,
    tariff: dict,
    business_name: str = "MAXIMODA",
    business_phone: str = "",
    genero_filter: str | None = None,
) -> str:
    """Genera el texto del tarifario listo para ticket térmico.

    Args:
        genero_filter: "NIÑO", "NIÑA", "HOMBRE", "MUJER" (o None para todos).
            Los productos sin género o marcados como UNISEX/ADULTO/MIXTO
            aparecen siempre, en cualquier filtro.
    """
    escuela = tariff.get("escuela_nombre", "")
    all_productos = tariff.get("productos", [])

    # Aplicar filtro de género
    filtro = genero_filter.strip().upper() if genero_filter else None
    if filtro:
        allowed = _GENERO_EQUIV.get(filtro, {filtro})
        productos = [
            p for p in all_productos
            if p.get("genero", "").upper() in _GENEROS_UNISEX
            or p.get("genero", "").upper() in allowed
        ]
    else:
        productos = all_productos

    lines: list[str] = []

    # — Encabezado —
    lines.append(business_name.center(_W))
    if business_phone:
        lines.append(f"Tel: {business_phone}".center(_W))
    lines.append("Lista de precios".center(_W))

    # — Escuela —
    lines.append(tk_top())
    lines.append(tk_center(escuela[:_IW]))
    if filtro:
        _GENERO_LABEL = {
            "NIÑO": "Niño", "NIÑA": "Niña",
            "HOMBRE": "Hombre", "MUJER": "Mujer",
        }
        lines.append(tk_center(_GENERO_LABEL.get(filtro, filtro.capitalize())))
    lines.append(tk_dbl())

    # — Productos agrupados por sección (tipo_prenda) —
    sections = _group_by_section(productos)
    show_headers = len(sections) > 1
    first_global = True

    for sec_name, sec_prods in sections:
        first_in_section = True

        for prod in sec_prods:
            nombre = prod.get("nombre", "")
            tallas = prod.get("tallas", [])
            if not tallas:
                continue

            if first_global:
                first_global = False
            else:
                lines.append(tk_mid())

            # Encabezado de sección al primer producto del grupo
            if show_headers and first_in_section:
                label = (sec_name or "Otros").upper()
                lines.append(tk_center(label))
                lines.append(tk_dbl())
                first_in_section = False

            # Nombre del producto
            for dl in textwrap.wrap(str(nombre), width=_IW) or [str(nombre)]:
                lines.append(tk_line(dl))

            # Agrupar tallas por precio como rangos compactos
            price_groups = _group_tallas_by_price(tallas)
            for precio, group_tallas in price_groups:
                tallas_str = _compact_talla_range(group_tallas)
                price_str = f"${tk_fmt(precio)}"
                label = f"  {tallas_str}"
                if len(label) + 1 + len(price_str) <= _IW:
                    lines.append(tk_row(label, price_str))
                else:
                    for chunk in textwrap.wrap(label, width=_IW):
                        lines.append(tk_line(chunk))
                    lines.append(tk_line(price_str.rjust(_IW)))

    lines.append(tk_bot())

    # — Pie —
    lines.append("")
    lines.append("Tallas en numeros pares".center(_W))
    lines.append("(4, 6, 8, 10...)".center(_W))
    lines.append("Precios sujetos a cambio".center(_W))
    lines.append("sin previo aviso.".center(_W))

    return "\n".join(lines)


def _group_by_section(productos: list[dict]) -> list[tuple[str, list[dict]]]:
    """Agrupa productos por tipo_prenda preservando el orden de entrada."""
    groups: list[tuple[str, list[dict]]] = []
    for p in productos:
        sec = p.get("tipo_prenda", "") or ""
        if groups and groups[-1][0] == sec:
            groups[-1][1].append(p)
        else:
            groups.append((sec, [p]))
    return groups


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


def _compact_talla_range(tallas: list[str]) -> str:
    """Convierte lista de tallas en rango compacto.

    Ejemplos:
        ["4", "6", "8", "10"] → "4 a 10"
        ["CH", "M", "G"]      → "CH a G"
        ["4"]                  → "4"
        ["CH"]                 → "CH"
        ["4", "8"]             → "4, 8"  (no consecutivas)
    """
    if len(tallas) <= 1:
        return tallas[0] if tallas else ""
    # Intentar detectar secuencia numérica
    nums = []
    for t in tallas:
        try:
            nums.append(int(t))
        except ValueError:
            nums = []
            break
    if nums and len(nums) >= 3:
        # Verificar si son consecutivos (paso uniforme)
        step = nums[1] - nums[0]
        is_sequence = all(nums[i + 1] - nums[i] == step for i in range(len(nums) - 1))
        if is_sequence:
            return f"{tallas[0]} a {tallas[-1]}"
    # Tallas letra: si >= 3, usar rango
    if not nums and len(tallas) >= 3:
        return f"{tallas[0]} a {tallas[-1]}"
    # Fallback: listar
    return ", ".join(tallas)
