#!/usr/bin/env python3
"""Genera Tarifario por Escuela — un PDF con una página por escuela.

Cada página lista los productos disponibles para esa escuela
agrupados por tipo de pieza, con rangos de tallas y precios.

Uso:
    python scripts/generar_tarifario_escuelas.py
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
from fpdf import FPDF

# ── Constantes ───────────────────────────────────────────────────────────────

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "tarifarios"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TALLA_ORDER = [
    "2", "4", "6", "8", "10", "12", "14", "16", "18",
    "20", "22", "24", "26", "28", "30", "32", "34", "36", "38",
    "40", "42", "44", "46",
    "XCH", "CH", "MD", "M", "GD", "G", "EXG", "XL", "2XL", "3XL",
    "U", "Uni", "Unitalla",
]

# Paleta — colores base
NAVY        = (30, 58, 110)     # #1E3A6E
DARK_TEXT    = (22, 32, 46)     # #16202E
GRAY_TEXT    = (51, 65, 85)     # #334155
WHITE       = (255, 255, 255)
ROW_WHITE   = (255, 255, 255)

# ── Paleta por tipo de pieza ─────────────────────────────────────────────────
# Familias visuales coherentes — distinguibles en < 1 segundo.
# Tupla: (accent_bar, header_bg, row_alt, title_color, price_color, line_color)
#
# DEPORTIVOS / EXTERIORES — teal
# SUPERIORES             — azul → púrpura
# INFERIORES             — slate / terracota
# ACCESORIOS             — ámbar / gris neutro

_PIEZA_COLORS: dict[str, tuple] = {
    # ── Deportivos / Exteriores ──────────────────────────────────────────────
    # Pants — teal brillante  #0F766E
    "Pants 3pz":     ((15, 118, 110), (223, 245, 242), (239, 250, 248), (10, 90, 84),   (10, 90, 84),   (180, 220, 215)),
    "Pants 2pz":     ((15, 118, 110), (223, 245, 242), (239, 250, 248), (10, 90, 84),   (10, 90, 84),   (180, 220, 215)),
    "Pants Suelto":  ((15, 118, 110), (223, 245, 242), (239, 250, 248), (10, 90, 84),   (10, 90, 84),   (180, 220, 215)),
    # Chamarra — teal profundo  #115E59
    "Chamarra":      ((17, 94, 89),   (204, 251, 241), (228, 253, 248), (12, 72, 68),   (12, 72, 68),   (168, 216, 208)),

    # ── Superiores ───────────────────────────────────────────────────────────
    # Playera — azul vivo  #2563EB
    "Playera":       ((37, 99, 235),  (232, 241, 255), (244, 248, 255), (28, 76, 188),  (28, 76, 188),  (195, 210, 238)),
    "Playera Polo":  ((37, 99, 235),  (232, 241, 255), (244, 248, 255), (28, 76, 188),  (28, 76, 188),  (195, 210, 238)),
    # Camisa — sky blue  #0284C7
    "Camisa":        ((2, 132, 199),  (224, 242, 254), (240, 249, 254), (2, 102, 155),  (2, 102, 155),  (185, 210, 230)),
    # Suéter — púrpura  #9333EA
    "Suéter":        ((147, 51, 234), (243, 232, 255), (249, 244, 255), (115, 38, 185), (115, 38, 185), (205, 195, 225)),
    # Chaleco — violeta  #7C3AED
    "Chaleco":       ((124, 58, 237), (237, 233, 254), (244, 242, 254), (96, 44, 188),  (96, 44, 188),  (200, 195, 222)),

    # ── Inferiores ───────────────────────────────────────────────────────────
    # Pantalón — slate  #475569
    "Pantalón":      ((71, 85, 105),  (226, 232, 240), (240, 243, 248), (54, 66, 82),   (54, 66, 82),   (190, 198, 210)),
    # Falda / Jumper — terracota  #7C2D12
    "Falda":         ((124, 45, 18),  (253, 231, 231), (254, 243, 243), (98, 34, 12),   (98, 34, 12),   (215, 195, 195)),
    "Jumper":        ((124, 45, 18),  (253, 231, 231), (254, 243, 243), (98, 34, 12),   (98, 34, 12),   (215, 195, 195)),

    # ── Accesorios / Complementos ────────────────────────────────────────────
    # Accesorios — ámbar  #A16207
    "Corbata":       ((161, 98, 7),   (254, 243, 199), (254, 249, 226), (128, 76, 5),   (128, 76, 5),   (215, 205, 170)),
    "Corbatín":      ((161, 98, 7),   (254, 243, 199), (254, 249, 226), (128, 76, 5),   (128, 76, 5),   (215, 205, 170)),
    "Moño":          ((161, 98, 7),   (254, 243, 199), (254, 249, 226), (128, 76, 5),   (128, 76, 5),   (215, 205, 170)),
    "Mascada":       ((161, 98, 7),   (254, 243, 199), (254, 249, 226), (128, 76, 5),   (128, 76, 5),   (215, 205, 170)),
    # Calceta / Short — gris neutro  #6B7280
    "Calceta":       ((107, 114, 128),(243, 244, 246), (249, 250, 251), (82, 88, 100),  (82, 88, 100),  (205, 208, 212)),
    "Short":         ((107, 114, 128),(243, 244, 246), (249, 250, 251), (82, 88, 100),  (82, 88, 100),  (205, 208, 212)),
}

# Default para tipos no listados — azul neutro
_DEFAULT_COLORS = ((37, 99, 235), (232, 241, 255), (244, 248, 255), (28, 76, 188), (28, 76, 188), (195, 210, 238))


def _colors_for(tipo: str) -> tuple:
    """Retorna (accent_bar, header_bg, row_alt, title_color, price_color, line_color)."""
    return _PIEZA_COLORS.get(tipo, _DEFAULT_COLORS)

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def talla_sort_key(t: str) -> tuple:
    try:
        idx = TALLA_ORDER.index(t)
    except ValueError:
        idx = 999
    return (idx, t)


def format_talla_range(tallas: list[str]) -> str:
    """Agrupa tallas contiguas en rangos: ['10','12','14','16'] → '10 – 16'."""
    sorted_t = sorted(tallas, key=talla_sort_key)
    if len(sorted_t) <= 3:
        return ", ".join(sorted_t)

    # Check if they're all consecutive in TALLA_ORDER
    indices = []
    for t in sorted_t:
        try:
            indices.append(TALLA_ORDER.index(t))
        except ValueError:
            return ", ".join(sorted_t)

    if not indices:
        return ", ".join(sorted_t)

    # Check contiguity
    is_contiguous = all(
        indices[i + 1] - indices[i] == 1 for i in range(len(indices) - 1)
    )
    if is_contiguous and len(sorted_t) > 3:
        return f"{sorted_t[0]} - {sorted_t[-1]}"

    return ", ".join(sorted_t)


def format_price(precio: Decimal) -> str:
    """$235 o $1,250."""
    p = int(precio)
    if p >= 1000:
        return f"${p:,}"
    return f"${p}"


# ── Pieza ordering ───────────────────────────────────────────────────────────

PIEZA_ORDER = [
    "Pants 3pz", "Pants 2pz", "Pants Suelto", "Chamarra", "Playera",
    "Playera Polo", "Suéter", "Camisa", "Chaleco", "Falda", "Jumper",
    "Pantalón", "Corbata", "Corbatín", "Moño", "Mascada", "Calceta", "Short",
]

def pieza_sort_key(tipo: str) -> tuple:
    try:
        idx = PIEZA_ORDER.index(tipo)
    except ValueError:
        idx = 999
    return (idx, tipo)


NIVEL_ORDER = ["Preescolar", "Primaria", "Secundaria", "Bachillerato", "General"]


def nivel_sort_key(nivel: str) -> tuple:
    try:
        idx = NIVEL_ORDER.index(nivel)
    except ValueError:
        idx = 998
    return (idx, nivel)


# ── Data fetch ───────────────────────────────────────────────────────────────

def fetch_schools_data(conn) -> dict[str, list[dict]]:
    """
    Retorna {escuela_nombre: [
        {tipo_pieza, nombre_base, talla, precio_venta}, ...
    ]} con productos directos + catálogo.
    """
    cur = conn.cursor()

    # Products linked directly via escuela_id
    cur.execute("""
        SELECT e.nombre AS escuela, tp.nombre AS tipo_pieza,
               p.nombre_base, v.talla, v.precio_venta,
               COALESCE(ne.nombre, 'General') AS nivel
        FROM variante v
        JOIN producto p ON p.id = v.producto_id
        JOIN tipo_pieza tp ON tp.id = p.tipo_pieza_id
        JOIN escuela e ON e.id = p.escuela_id
        LEFT JOIN nivel_educativo ne ON ne.id = p.nivel_educativo_id
        WHERE v.activo = true AND p.activo = true AND e.activo = true
        ORDER BY e.nombre, tp.nombre, p.nombre_base, v.talla
    """)
    direct = cur.fetchall()

    # Products linked via catalog_school_product_link
    cur.execute("""
        SELECT e.nombre AS escuela, tp.nombre AS tipo_pieza,
               p.nombre_base, v.talla, v.precio_venta,
               COALESCE(ne.nombre, 'General') AS nivel
        FROM variante v
        JOIN producto p ON p.id = v.producto_id
        JOIN tipo_pieza tp ON tp.id = p.tipo_pieza_id
        JOIN catalog_school_product_link cspl ON cspl.producto_id = p.id AND cspl.activo = true
        JOIN escuela e ON e.id = cspl.escuela_id AND e.activo = true
        LEFT JOIN nivel_educativo ne ON ne.id = p.nivel_educativo_id
        WHERE v.activo = true AND p.activo = true
        ORDER BY e.nombre, tp.nombre, p.nombre_base, v.talla
    """)
    catalog = cur.fetchall()

    # Merge deduplicating
    all_rows: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple] = set()

    for is_catalog, source in ((False, direct), (True, catalog)):
        for escuela, tipo, nombre, talla, precio, nivel in source:
            key = (escuela, tipo, nombre, talla)
            if key not in seen:
                seen.add(key)
                all_rows[escuela].append({
                    "tipo_pieza": tipo,
                    "nombre_base": nombre,
                    "talla": talla,
                    "precio": precio,
                    "nivel": nivel,
                    "catalog": is_catalog,
                })

    return dict(sorted(all_rows.items()))


def group_school_products(rows: list[dict]) -> list[dict]:
    """
    Agrupa rows de una escuela en estructura:
    [
        {
            "tipo_pieza": "Playera",
            "productos": [
                {
                    "nombre": "Playera Deportiva Frida Kahlo",
                    "rangos": [
                        {"tallas": "4, 6, 8, 10", "precio": "$195"},
                        ...
                    ]
                },
                ...
            ]
        },
        ...
    ]
    """
    # Group by tipo -> producto -> precio -> tallas
    by_tipo: dict[str, dict[str, dict[Decimal, list[str]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for r in rows:
        by_tipo[r["tipo_pieza"]][r["nombre_base"]][r["precio"]].append(r["talla"])

    result = []
    for tipo in sorted(by_tipo.keys(), key=pieza_sort_key):
        productos = []
        for nombre in sorted(by_tipo[tipo].keys()):
            rangos = []
            for precio in sorted(by_tipo[tipo][nombre].keys()):
                tallas = by_tipo[tipo][nombre][precio]
                rangos.append({
                    "tallas": format_talla_range(tallas),
                    "precio": format_price(precio),
                })
            productos.append({"nombre": nombre, "rangos": rangos})
        result.append({"tipo_pieza": tipo, "productos": productos})

    return result


def group_school_products_by_nivel(
    rows: list[dict],
) -> list[tuple[str, list[dict]]]:
    """Group rows by nivel_educativo, then by tipo_pieza within each nivel.

    Returns [(nivel_name, [groups])] sorted by NIVEL_ORDER.

    Smart merging: if a school has only ONE real nivel + "General" catalog
    products, the General rows are folded into that nivel (no banners shown).
    Banners only appear when there are 2+ distinct real niveles.

    Catalog-only niveles: if a nivel has ONLY catalog products (no direct
    school products), those rows are reclassified as "General" to avoid
    orphaned nivel sections.
    """
    # First pass: collect niveles that have direct (non-catalog) products
    direct_niveles: set[str] = set()
    for r in rows:
        if not r.get("catalog", False):
            direct_niveles.add(r.get("nivel", "General"))

    # Second pass: group rows, reclassifying catalog-only niveles to General
    by_nivel: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        nivel = r.get("nivel", "General")
        if nivel != "General" and nivel not in direct_niveles and r.get("catalog"):
            nivel = "General"
        by_nivel[nivel].append(r)

    real_niveles = [n for n in by_nivel if n != "General"]

    # If only one real nivel + General → merge General into that nivel
    if len(real_niveles) == 1 and "General" in by_nivel:
        merged = by_nivel[real_niveles[0]] + by_nivel["General"]
        groups = group_school_products(merged)
        return [(real_niveles[0], groups)] if groups else []

    # If no real niveles (all General) → single section, no banner
    if not real_niveles:
        groups = group_school_products(rows)
        return [("General", groups)] if groups else []

    # Multiple real niveles — keep separated (General stays separate too)
    result: list[tuple[str, list[dict]]] = []
    for nivel in sorted(by_nivel.keys(), key=nivel_sort_key):
        groups = group_school_products(by_nivel[nivel])
        if groups:
            result.append((nivel, groups))
    return result


# ── PDF Generation ───────────────────────────────────────────────────────────

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_ITALIC_PATH = "/System/Library/Fonts/Supplemental/Arial Italic.ttf"


class TarifarioPDF(FPDF):
    """Custom FPDF with header/footer and Unicode support."""

    def __init__(self, updated_text: str):
        super().__init__(orientation="L", unit="mm", format="Letter")
        self.updated_text = updated_text
        self.current_school = ""
        self.set_auto_page_break(auto=False)
        # Register Unicode font
        self.add_font("Arial", "", FONT_PATH)
        self.add_font("Arial", "B", FONT_BOLD_PATH)
        self.add_font("Arial", "I", FONT_ITALIC_PATH)

    def header(self):
        if not self.current_school:
            return
        # Navy banner full width
        w = self.w - 20  # margins
        self.set_fill_color(*NAVY)
        self.rect(10, 8, w, 14, "F")

        # School name
        self.set_xy(14, 9)
        self.set_font("Arial", "B", 14)
        self.set_text_color(*WHITE)
        self.cell(w - 70, 12, self.current_school.upper(), align="L")

        # Updated date
        self.set_font("Arial", "", 8)
        self.set_text_color(157, 195, 230)
        self.cell(66, 12, self.updated_text, align="R")

        # Subtitle
        self.set_xy(10, 23)
        self.set_font("Arial", "", 7)
        self.set_text_color(*GRAY_TEXT)
        self.cell(w, 4, "TARIFARIO DE UNIFORMES", align="L")

        self.ln(8)

    def footer(self):
        self.set_y(-12)
        self.set_font("Arial", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", align="C")


def _estimate_groups_height(groups: list[dict],
                            school: str = "") -> float:
    """Estimate mm height needed to render a list of groups."""
    h = 0.0
    for g in groups:
        h += 7 + 5.5 + 3  # section header + col headers + spacing
        for p in g["productos"]:
            short = _shorten_product_name(p["nombre"], g["tipo_pieza"], school)
            if short:
                h += 5  # product sub-header
            h += 6 * len(p["rangos"])  # data rows
    return h


def _render_two_col_paginated(pdf: TarifarioPDF, groups: list[dict],
                               group_heights: list[float],
                               col_w: float, col_gap: float,
                               available_h: float,
                               nivel: str | None = None,
                               school: str = ""):
    """Render groups across multiple pages, always in two columns.

    If *nivel* is given (multi-nivel school), the nivel banner is
    re-rendered on every overflow page so the reader always knows
    which nivel the products belong to.
    """
    remaining = list(range(len(groups)))  # indices of groups still to render
    page_w = pdf.w - 20

    while remaining:
        page_avail = available_h
        left_batch: list[int] = []
        right_batch: list[int] = []
        left_used = 0.0
        right_used = 0.0

        # Greedily fill left column, then right column
        for idx in list(remaining):
            h = group_heights[idx]
            if left_used + h <= page_avail:
                left_batch.append(idx)
                left_used += h
            elif right_used + h <= page_avail:
                right_batch.append(idx)
                right_used += h
            else:
                break  # doesn't fit on this page

        placed = set(left_batch + right_batch)
        if not placed:
            # Single group too tall — force it into left column, let it overflow
            idx = remaining[0]
            left_batch.append(idx)
            placed.add(idx)

        remaining = [i for i in remaining if i not in placed]

        y_before = pdf.get_y()

        # Left column
        _render_groups_column(pdf, [groups[i] for i in left_batch],
                              x_start=10, col_w=col_w, school=school)
        y_after_left = pdf.get_y()

        # Right column
        if right_batch:
            pdf.set_y(y_before)
            _render_groups_column(pdf, [groups[i] for i in right_batch],
                                  x_start=10 + col_w + col_gap, col_w=col_w,
                                  school=school)
            y_after_right = pdf.get_y()
            pdf.set_y(max(y_after_left, y_after_right))

        if remaining:
            # Only add page if current page doesn't have enough space
            # (the column renderer may have already added overflow pages)
            space_left = pdf.h - pdf.get_y() - 15
            if space_left < 30:
                pdf.add_page()
            if nivel:
                _render_nivel_banner(pdf, nivel + " (cont.)", page_w)
            available_h = pdf.h - pdf.get_y() - 15


# Colores para banners de nivel educativo
NIVEL_COLORS: dict[str, tuple[tuple, tuple]] = {
    "Preescolar":   ((56, 124, 68),  (218, 238, 220)),
    "Primaria":     ((44, 100, 165), (215, 230, 248)),
    "Secundaria":   ((140, 70, 50),  (245, 225, 218)),
    "Bachillerato": ((110, 60, 130), (235, 222, 245)),
    "General":      ((90, 100, 115), (232, 235, 240)),
}


def _render_nivel_banner(pdf: TarifarioPDF, nivel: str, page_w: float):
    """Render a nivel educativo section banner."""
    accent, _ = NIVEL_COLORS.get(nivel, NIVEL_COLORS["General"])
    y = pdf.get_y() + 1
    pdf.set_fill_color(*accent)
    pdf.rect(10, y, page_w, 7, "F")
    pdf.set_xy(14, y + 0.5)
    pdf.set_font("Arial", "B", 8.5)
    pdf.set_text_color(*WHITE)
    pdf.cell(page_w - 8, 6, nivel.upper(), align="L")
    pdf.set_y(y + 9)


def render_school_page(pdf: TarifarioPDF, school_name: str,
                       nivel_sections: list[tuple[str, list[dict]]]):
    """Render page(s) for a school — two columns, with nivel banners if multi-nivel."""
    pdf.current_school = school_name
    pdf.add_page()

    page_w = pdf.w - 20  # effective width (margins 10mm each side)
    col_gap = 8
    col_w = (page_w - col_gap) / 2
    is_multi = len(nivel_sections) > 1

    for si, (nivel, groups) in enumerate(nivel_sections):
        if is_multi:
            # Ensure enough room for nivel banner + header + several rows
            if pdf.get_y() + 55 > pdf.h - 15:
                pdf.add_page()
            _render_nivel_banner(pdf, nivel, page_w)

        available_h = pdf.h - pdf.get_y() - 15

        # Calculate group heights
        group_heights = []
        for g in groups:
            h = 7 + 5.5 + 3
            for p in g["productos"]:
                short = _shorten_product_name(p["nombre"], g["tipo_pieza"], school_name)
                if short:
                    h += 5
                h += 6 * len(p["rangos"])
            group_heights.append(h)

        total_h = sum(group_heights)

        # Find best split point — balance column heights
        best_split = 1
        best_diff = float("inf")
        cum = 0.0
        for i, h in enumerate(group_heights):
            cum += h
            diff = abs(cum - (total_h - cum))
            if diff < best_diff:
                best_diff = diff
                best_split = i + 1

        best_split = max(1, min(best_split, len(groups) - 1)) if len(groups) > 1 else 1

        left_groups = groups[:best_split]
        right_groups = groups[best_split:] if best_split < len(groups) else []

        left_h = sum(group_heights[:best_split])
        right_h = sum(group_heights[best_split:])
        max_col_h = max(left_h, right_h)

        if max_col_h <= available_h:
            y_before = pdf.get_y()
            _render_groups_column(pdf, left_groups, x_start=10, col_w=col_w,
                                  school=school_name)
            y_after_left = pdf.get_y()

            if right_groups:
                pdf.set_y(y_before)
                _render_groups_column(pdf, right_groups,
                                      x_start=10 + col_w + col_gap, col_w=col_w,
                                      school=school_name)
                y_after_right = pdf.get_y()
                pdf.set_y(max(y_after_left, y_after_right))
        else:
            _render_two_col_paginated(pdf, groups, group_heights,
                                      col_w, col_gap, available_h,
                                      nivel=nivel if is_multi else None,
                                      school=school_name)


def _render_section_header(pdf: TarifarioPDF, tipo: str, colors: tuple,
                            x_start: float, col_w: float,
                            tallas_w: float, precio_w: float,
                            y: float, cont: bool = False) -> float:
    """Render section header bar + column headers. Returns new y."""
    accent_bar, header_bg, _, title_clr, _, _ = colors
    label = tipo.upper() + (" (cont.)" if cont else "")

    pdf.set_xy(x_start, y)
    pdf.set_fill_color(*accent_bar)
    pdf.rect(x_start, y, 2, 7, "F")
    pdf.set_fill_color(*header_bg)
    pdf.rect(x_start + 2, y, col_w - 2, 7, "F")
    pdf.set_xy(x_start + 5, y + 0.5)
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(*title_clr)
    pdf.cell(tallas_w - 5, 6, label, align="L")

    y += 7
    col_hdr_bg = tuple(min(255, c + 12) for c in header_bg)
    pdf.set_fill_color(*col_hdr_bg)
    pdf.rect(x_start, y, col_w, 5.5, "F")
    pdf.set_xy(x_start + 5, y + 0.5)
    pdf.set_font("Arial", "B", 7)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.cell(tallas_w - 5, 4.5, "TALLAS", align="L")
    pdf.cell(precio_w, 4.5, "PRECIO", align="C")

    return y + 5.5


def _render_groups_column(pdf: TarifarioPDF, groups: list[dict],
                          x_start: float, col_w: float,
                          school: str = ""):
    """Render a list of tipo_pieza groups in a column.

    Handles page overflow within a group by re-rendering section
    headers on the new page so rows never appear orphaned.
    """
    tallas_w = col_w * 0.65
    precio_w = col_w * 0.35
    page_bottom = pdf.h - 15  # margin

    for gi, group in enumerate(groups):
        tipo = group["tipo_pieza"]
        colors = _colors_for(tipo)
        accent_bar, header_bg, row_alt, title_clr, price_clr, line_clr = colors

        y = pdf.get_y()

        # Check if header + at least 1 row fits
        if y + 7 + 5.5 + 6 > page_bottom:
            pdf.add_page()
            y = pdf.get_y()

        y = _render_section_header(pdf, tipo, colors, x_start, col_w,
                                    tallas_w, precio_w, y)

        # Products
        row_idx = 0
        for pi, prod in enumerate(group["productos"]):
            short_name = _shorten_product_name(prod["nombre"], tipo, school)

            if short_name:
                # Check fit for sub-header + at least 1 row
                if y + 5 + 6 > page_bottom:
                    pdf.add_page()
                    y = _render_section_header(pdf, tipo, colors, x_start,
                                               col_w, tallas_w, precio_w,
                                               pdf.get_y(), cont=True)
                pdf.set_fill_color(248, 250, 253)
                pdf.rect(x_start, y, col_w, 5, "F")
                pdf.set_xy(x_start + 5, y + 0.3)
                pdf.set_font("Arial", "I", 7)
                pdf.set_text_color(*accent_bar)
                pdf.cell(col_w - 5, 4.5, short_name, align="L")
                y += 5

            for ri, rango in enumerate(prod["rangos"]):
                # Check if row fits on current page
                if y + 6 > page_bottom:
                    pdf.add_page()
                    y = _render_section_header(pdf, tipo, colors, x_start,
                                               col_w, tallas_w, precio_w,
                                               pdf.get_y(), cont=True)
                    if short_name:
                        pdf.set_fill_color(248, 250, 253)
                        pdf.rect(x_start, y, col_w, 5, "F")
                        pdf.set_xy(x_start + 5, y + 0.3)
                        pdf.set_font("Arial", "I", 7)
                        pdf.set_text_color(*accent_bar)
                        pdf.cell(col_w - 5, 4.5, short_name + " (cont.)", align="L")
                        y += 5

                # Alternate row colors
                bg = row_alt if row_idx % 2 == 0 else ROW_WHITE
                pdf.set_fill_color(*bg)
                pdf.rect(x_start, y, col_w, 6, "F")

                # Subtle line
                pdf.set_draw_color(*line_clr)
                pdf.line(x_start + 3, y, x_start + col_w - 3, y)

                # Tallas
                pdf.set_xy(x_start + 5, y + 0.8)
                pdf.set_font("Arial", "", 8.5)
                pdf.set_text_color(*DARK_TEXT)
                pdf.cell(tallas_w - 5, 4.5, rango["tallas"], align="L")

                # Precio
                pdf.set_font("Arial", "B", 9)
                pdf.set_text_color(*price_clr)
                pdf.cell(precio_w, 4.5, rango["precio"], align="C")

                y += 6
                row_idx += 1

        # Spacing between tipo groups
        y += 3
        pdf.set_y(y)


def _shorten_product_name(nombre: str, tipo: str,
                          school: str = "") -> str:
    """Shorten 'Playera Deportiva Frida Kahlo' → 'Deportiva'.

    Strips tipo prefix, pipe suffixes (| Oficial | …), and school name.
    Returns empty string when nothing descriptive remains.
    """
    short = nombre
    # Remove pipe suffix  (e.g. "… | Oficial | Camisa")
    if " | " in short:
        short = short.split(" | ")[0].strip()
    # Remove tipo prefix
    if short.startswith(tipo + " "):
        short = short[len(tipo) + 1:]
    # Remove "Ad Hoc " prefix
    short = short.replace("Ad Hoc ", "")
    # Remove school name
    if school and school in short:
        short = short.replace(school, "").strip()
    # Clean up double spaces and trailing dashes
    short = re.sub(r"\s{2,}", " ", short).strip(" -")
    # Truncate very long names
    parts = short.split()
    if len(parts) > 5:
        short = " ".join(parts[:5]) + "…"
    return short


# ── Portada e Índice ─────────────────────────────────────────────────────────

# Agrupación de piezas por categoría para la leyenda — orden por familias visuales
_LEGEND_GROUPS = [
    # Deportivos / Exteriores
    ("Pants",            ["Pants 3pz", "Pants 2pz", "Pants Suelto"]),
    ("Chamarra",         ["Chamarra"]),
    # Superiores
    ("Playera",          ["Playera", "Playera Polo"]),
    ("Camisa",           ["Camisa"]),
    ("Suéter",           ["Suéter"]),
    ("Chaleco",          ["Chaleco"]),
    # Inferiores
    ("Pantalón",         ["Pantalón"]),
    ("Falda / Jumper",   ["Falda", "Jumper"]),
    # Accesorios / Complementos
    ("Accesorios",       ["Corbata", "Corbatín", "Moño", "Mascada"]),
    ("Calceta / Short",  ["Calceta", "Short"]),
]


def _render_cover(pdf: TarifarioPDF, updated: str, year: int):
    """Render cover page with title + color legend."""
    pdf.current_school = ""  # suppress school header
    pdf.add_page()

    page_w = pdf.w - 20

    # Title banner
    pdf.set_fill_color(*NAVY)
    pdf.rect(10, 30, page_w, 28, "F")
    pdf.set_xy(10, 33)
    pdf.set_font("Arial", "B", 24)
    pdf.set_text_color(*WHITE)
    pdf.cell(page_w, 12, f"TARIFARIO DE UNIFORMES {year}", align="C")
    pdf.set_xy(10, 46)
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(180, 200, 225)
    pdf.cell(page_w, 8, "Precios por escuela  ·  Satélite Uniformes", align="C")

    # Updated date
    pdf.set_xy(10, 63)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.cell(page_w, 6, updated, align="C")

    # ── Instrucciones ─────────────────────────────────────────────────────
    y = 78
    pdf.set_xy(10, y)
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*NAVY)
    pdf.cell(page_w, 7, "Cómo leer este documento", align="L")
    y += 9

    instructions = [
        "Cada escuela tiene su propia página con todos los productos disponibles.",
        "Los productos están organizados en dos columnas, agrupados por tipo de pieza.",
        "Cada tipo de pieza tiene un color distinto para facilitar su identificación rápida.",
        "La columna TALLAS muestra los rangos disponibles y PRECIO el costo por pieza.",
        "Cuando un tipo tiene varias variantes (ej. dos suéteres), se muestra el nombre debajo del encabezado.",
    ]
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*DARK_TEXT)
    for inst in instructions:
        pdf.set_xy(14, y)
        pdf.cell(3, 5, "•", align="L")
        pdf.cell(page_w - 8, 5, inst, align="L")
        y += 6.5

    # ── Leyenda de colores ────────────────────────────────────────────────
    y += 6
    pdf.set_xy(10, y)
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*NAVY)
    pdf.cell(page_w, 7, "Guía de colores por tipo de pieza", align="L")
    y += 10

    # Render in two columns
    col_w = (page_w - 10) / 2
    items_per_col = (len(_LEGEND_GROUPS) + 1) // 2
    y_start = y

    for i, (label, tipos) in enumerate(_LEGEND_GROUPS):
        col = 0 if i < items_per_col else 1
        row = i if col == 0 else i - items_per_col
        x = 14 + col * (col_w + 10)
        cy = y_start + row * 14

        accent, header_bg, _, title_clr, _, _ = _colors_for(tipos[0])

        # Color swatch
        pdf.set_fill_color(*accent)
        pdf.rect(x, cy, 3, 10, "F")
        pdf.set_fill_color(*header_bg)
        pdf.rect(x + 3, cy, col_w - 6, 10, "F")

        # Label
        pdf.set_xy(x + 7, cy + 1.5)
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(*title_clr)
        pdf.cell(col_w * 0.45, 7, label, align="L")

        # Subtypes
        pdf.set_font("Arial", "", 7.5)
        pdf.set_text_color(*GRAY_TEXT)
        subtext = ", ".join(tipos)
        pdf.cell(col_w * 0.45, 7, subtext, align="L")


def _render_index_placeholder(pdf: TarifarioPDF):
    """Add blank page(s) for the index — content filled later."""
    pdf.current_school = ""
    pdf.add_page()
    # We'll overwrite this page content in _rewrite_index


def _rewrite_index(pdf: TarifarioPDF, school_pages: list[tuple[str, int]],
                   index_page_num: int):
    """Overwrite index page(s) with the actual school→page mapping."""
    # fpdf2 allows drawing on existing pages via pdf.page = N
    last_page = pdf.page
    pdf.page = index_page_num

    page_w = pdf.w - 20

    # Clear page by drawing white rect
    pdf.set_fill_color(*WHITE)
    pdf.rect(0, 0, pdf.w, pdf.h, "F")

    # Title
    y = 12
    pdf.set_xy(10, y)
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(*NAVY)
    pdf.cell(page_w, 10, "ÍNDICE DE ESCUELAS", align="C")
    y += 16

    # Subtitle line
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.5)
    pdf.line(10, y, 10 + page_w, y)
    y += 6

    # Three-column index for compactness
    n_cols = 3
    col_w = (page_w - 8) / n_cols  # gap between cols
    items_per_col = (len(school_pages) + n_cols - 1) // n_cols
    row_h = 7
    y_start = y

    for i, (name, pg) in enumerate(school_pages):
        col = i // items_per_col
        row = i % items_per_col
        x = 12 + col * (col_w + 4)
        ry = y_start + row * row_h

        # Check if we'd go off page
        if ry + row_h > pdf.h - 15:
            continue  # skip if too many (shouldn't happen with 48 schools)

        # Alternating row bg
        if row % 2 == 0:
            pdf.set_fill_color(245, 247, 252)
            pdf.rect(x - 2, ry, col_w, row_h, "F")

        # School name
        pdf.set_xy(x, ry + 1)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(*DARK_TEXT)
        # Truncate very long names
        display_name = name if len(name) <= 30 else name[:28] + "…"
        pdf.cell(col_w - 18, 5, display_name, align="L")

        # Page number with dots
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(*NAVY)
        pdf.cell(14, 5, str(pg), align="R")

    # General tarifario reference
    max_y = y_start + items_per_col * row_h + 8
    pdf.set_draw_color(180, 190, 210)
    pdf.line(12, max_y, 12 + page_w - 4, max_y)
    max_y += 4
    pdf.set_xy(12, max_y)
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(*NAVY)
    general_pg = pdf.pages_count + 2  # +1 divider +1 (1-indexed)
    pdf.cell(page_w - 4, 6,
             f"Tarifario General (productos genéricos) .................. pág. {general_pg}",
             align="L")

    # Footer note
    pdf.set_xy(10, pdf.h - 18)
    pdf.set_font("Arial", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(page_w, 5, f"{len(school_pages)} escuelas  ·  {pdf.pages_count} páginas", align="C")

    # Restore page pointer to the last page
    pdf.page = last_page


# ── Tarifario General — datos y renderizado ─────────────────────────────────
# Precios de referencia por tipo de pieza (hardcoded — no vienen de la BD).

# Colores para secciones de excepciones
_EXC_COLORS = ((180, 50, 50), (252, 230, 230), (254, 242, 242),
               (155, 35, 35), (155, 35, 35), (235, 205, 205))

# Shorthand builder
def _s(title, headers, rows):
    return {"title": title, "headers": headers, "rows": rows}

GENERAL_PAGES = [
    # ── 1. Playeras Deportivas ───────────────────────────────────────────
    {"title": "Playeras Deportivas", "tipo": "Playera", "cols": 4,
     "sections": [
         _s("Preescolar", ["Tallas", "Precio"],
            [["2, 4, 6, 8, 10", "$175"], ["12, 14, 16", "$199"],
             ["CH, MD, GD, EXG", "$219"]]),
         _s("Primaria", ["Tallas", "Precio"],
            [["4, 6, 8, 10", "$199"], ["12, 14, 16", "$209"],
             ["CH, MD, GD, EXG", "$219"]]),
         _s("Secundaria", ["Tallas", "Precio"],
            [["12, 14, 16", "$229"], ["CH, MD, GD, EXG", "$239"]]),
         _s("Bachillerato", ["Tallas", "Precio"],
            [["12, 14, 16", "$229"], ["CH, MD, GD, EXG", "$239"]]),
     ],
     "notes": ["Si una playera ya tiene precio mayor marcado, se respeta."]},

    # ── 2. Suéteres ──────────────────────────────────────────────────────
    {"title": "Suéteres", "tipo": "Suéter", "cols": 3,
     "sections": [
         _s("Básico", ["Tallas", "Precio"],
            [["4, 6, 8", "$289"], ["10, 12, 14, 16", "$299"],
             ["30, 32, 34", "$309"], ["36, 38, 40, 42", "$315"],
             ["44, 46", "$325"]]),
         _s("Oficial Preescolar", ["Tallas", "Precio"],
            [["4, 6, 8, 10", "$290"]]),
         _s("Oficial Primaria", ["Tallas", "Precio"],
            [["4, 6, 8, 10", "$290"], ["12, 14, 16", "$315"],
             ["30 - 42", "$325"]]),
         _s("Oficial Secundaria", ["Tallas", "Precio"],
            [["12, 14, 16", "$325"], ["30 - 44", "$345"]]),
         _s("Oficial Bachillerato", ["Tallas", "Precio"],
            [["14, 16", "$325"], ["32, 34", "$335"],
             ["36, 38", "$345"], ["40, 42, 44", "$355"]]),
     ],
     "exceptions": [
         _s("Exc. Preescolar", ["Escuela", "Tallas", "Precio"],
            [["Margarita Paz Paredes", "4, 6, 8, 10", "$315"]]),
         _s("Exc. Primaria", ["Escuela", "Tallas", "Precio"],
            [["Benito Juárez", "40, 42", "$335"],
             ["Colegio Motolinea", "40", "$335"],
             ["Francisco Villa", "40", "$335"],
             ["Ignacio Allende", "40", "$335"],
             ["Miguel Hidalgo", "40, 42", "$335"]]),
         _s("Exc. Bachillerato", ["Escuela", "Tallas", "Precio"],
            [["UVEG", "14-42", "$355"]]),
     ], "exc_cols": 3,
     "notes": ["Suéter Oferta Ad hoc Talla Uni se maneja aparte a $199.",
               "Si una escuela aparece en excepciones, respetar ese precio."]},

    # ── 3. Chamarras ─────────────────────────────────────────────────────
    {"title": "Chamarras", "tipo": "Chamarra", "cols": 3,
     "sections": [
         _s("Deportiva (Con Escudo)", ["Nivel", "Tallas", "Precio"],
            [["Preescolar", "4, 6, 8", "$315"],
             ["Primaria", "4-16, CH, MD, GD", "$335"],
             ["Secundaria", "12-16, CH-EXG", "$385"],
             ["Bachillerato", "12-16, CH-EXG", "$385"]]),
         _s("Básica Liso", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$175"], ["10, 12", "$195"],
             ["14, 16", "$215"], ["28, CH, MD, GD, EXG", "$235"]]),
         _s("Básica Punto", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$275"], ["10, 12, 14, 16", "$295"],
             ["28, CH", "$385"], ["MD", "$395"],
             ["GD", "$405"], ["EXG", "$415"]]),
     ],
     "notes": ["No heredar precios de Chamarra Básica a Chamarra Deportiva.",
               "Si una prenda ya tiene precio mayor marcado, se respeta."]},

    # ── 4. Chalecos ──────────────────────────────────────────────────────
    {"title": "Chalecos", "tipo": "Chaleco", "cols": 4,
     "sections": [
         _s("Básico", ["Tallas", "Precio"],
            [["4, 6, 8", "$229"], ["10, 12, 14, 16", "$239"],
             ["28, 30, 32, 34", "$259"], ["36 - 46", "$269"]]),
         _s("Oficial Primaria", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$240"], ["10, 12", "$245"],
             ["14, 16", "$250"], ["32-42, CH-EXG", "$270"]]),
         _s("Oficial Secundaria", ["Tallas", "Precio"],
            [["12, 14, 16", "$245"], ["30, 32, 34", "$265"],
             ["36 - 44", "$275"]]),
         _s("Oficial Bachillerato", ["Tallas", "Precio"],
            [["14, 16", "$265"], ["32, 34", "$275"],
             ["36 - 42", "$285"], ["44", "$295"]]),
     ],
     "exceptions": [
         _s("Exc. Primaria (1/2)", ["Escuela", "Tallas", "Precio"],
            [["Huizache", "6, 8", "$240"], ["Huizache", "10, 12", "$245"],
             ["Huizache", "14, 16", "$250"], ["Huizache", "34, 36", "$270"],
             ["Albino García Ramos", "36 - 42", "$290"]]),
         _s("Exc. Primaria (2/2)", ["Escuela", "Tallas", "Precio"],
            [["Francisco Villa", "10, 12", "$250"],
             ["Francisco Villa", "14, 16", "$260"],
             ["Francisco Villa", "34, 36", "$290"],
             ["Francisco Villa", "38, 40", "$300"],
             ["Justo Sierra", "36", "$275"], ["Justo Sierra", "38", "$280"],
             ["Miguel Campuzano", "34", "$280"],
             ["Miguel Hidalgo", "36, 38", "$275"],
             ["Miguel Hidalgo", "40, 42", "$285"]]),
     ], "exc_cols": 2,
     "notes": ["Huizache se normaliza con la escalera de Chaleco Oficial Primaria."]},

    # ── 5. Camisas ───────────────────────────────────────────────────────
    {"title": "Camisas", "tipo": "Camisa", "cols": 4,
     "sections": [
         _s("Básica MC Blanca", ["Tallas", "Precio"],
            [["4, 6, 8", "$89"], ["10 - 16", "$99"], ["28, 30", "$115"],
             ["32, 34", "$135"], ["36, 38", "$145"], ["40, 42", "$165"]]),
         _s("Prowear MC Blanca", ["Tallas", "Precio"],
            [["4, 6, 8", "$125"], ["10, 12", "$145"], ["14, 16", "$155"],
             ["28 - 38", "$165"], ["40, 42", "$185"]]),
         _s("M. Larga H Blanca", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$199"], ["10 - 18", "$219"],
             ["32, 34", "$239"], ["36, 38", "$249"],
             ["40-44, CH", "$259"], ["MD", "$269"],
             ["GD", "$279"], ["EXG", "$289"]]),
         _s("M. Larga M Blanca", ["Tallas", "Precio"],
            [["30, CH", "$269"], ["MD, GD", "$289"], ["EXG", "$309"]]),
         _s("Oficial Preescolar", ["Tallas", "Precio"],
            [["Línea completa", "$139"]]),
         _s("Oficial Primaria", ["Tallas", "Precio"],
            [["4, 6, 8, 10", "$215"], ["12, 14, 16", "$225"],
             ["32 - 38", "$245"]]),
         _s("Oficial Secundaria", ["Tallas", "Precio"],
            [["Línea completa", "$265"]]),
         _s("Oficial Bachillerato", ["Tallas", "Precio"],
            [["Línea completa", "$265"]]),
     ],
     "exceptions": [
         _s("Excepciones por escuela", ["Escuela", "Línea", "Precio"],
            [["Francisco Villa", "Ofi. Primaria", "215/225/245"],
             ["Bicentenario", "Ofi. Secundaria", "$265"],
             ["CBTIS 148", "Ofi. Bachillerato", "$265"],
             ["Conalep", "Ofi. Escolar", "$265"]]),
     ],
     "notes": ["Si aparece Camisa M. Larga Blanca a $265 sin nivel, conservar precio."]},

    # ── 6. Pants 2pz y 3pz ──────────────────────────────────────────────
    {"title": "Pants 2 Piezas y 3 Piezas", "tipo": "Pants 2pz", "cols": 4,
     "sections": [
         _s("Preescolar", ["Tallas", "2 pzas", "3 pzas"],
            [["2, 4, 6, 8, 10", "$445", "$545"]]),
         _s("Primaria", ["Tallas", "2 pzas", "3 pzas"],
            [["4-12", "$485", "$585"], ["14, 16", "$495", "$595"],
             ["CH, MD, GD", "$585", "$685"]]),
         _s("Secundaria", ["Tallas", "2 pzas", "3 pzas"],
            [["10, 12", "$595", "$695"], ["14, 16", "$605", "$705"],
             ["CH-EXG", "$615", "$715"]]),
         _s("Bachillerato", ["Tallas", "2 pzas", "3 pzas"],
            [["16", "$615", "$715"], ["CH-EXG", "$615", "$715"]]),
     ],
     "exceptions": [
         _s("Exc. Preescolar", ["Escuela", "2 pzas", "3 pzas"],
            [["Sor Juana Inés de la Cruz", "$515", "—"]]),
         _s("Exc. Primaria", ["Escuela", "2 pzas", "3 pzas"],
            [["Adolfo Lopez Mateo", "575/585/595", "—"],
             ["Colegio Motolinea", "595/630/640/650", "695/730/740/750"]]),
         _s("Exc. Sec. / Bach.", ["Escuela", "2 pzas", "3 pzas"],
            [["Telesecundaria 454", "$650", "$750"],
             ["Telesecundaria 512", "$650", "$750"],
             ["CECYTE", "$650", "$750"],
             ["Conalep", "$650", "$750"],
             ["UVEG", "$650", "$750"]]),
     ], "exc_cols": 3},

    # ── 7. Pants Suelto Básico ───────────────────────────────────────────
    {"title": "Pants Suelto Básico", "tipo": "Pants Suelto", "cols": 2,
     "sections": [
         _s("Liso", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$165"], ["10, 12, 14, 16", "$180"],
             ["28, CH", "$205"], ["MD", "$215"],
             ["GD", "$225"], ["EXG", "$235"]]),
         _s("Punto", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$249"], ["10, 12, 14, 16", "$269"],
             ["28, CH", "$309"], ["MD, GD", "$319"], ["EXG", "$339"]]),
     ],
     "notes": ["Liso y Punto son familias distintas — no mezclar escaleras."]},

    # ── 8. Pantalones ────────────────────────────────────────────────────
    {"title": "Pantalones", "tipo": "Pantalón", "cols": 3,
     "sections": [
         _s("Vestir", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$235"], ["10, 12, 14, 16", "$245"],
             ["18, 20, 28, 30", "$265"], ["32, 34", "$285"],
             ["36, 38, 40", "$295"], ["42, 44", "$315"]]),
         _s("Vestir Gris obscuro / claro", ["Tallas", "Precio"],
            [["4, 6, 8", "$235"], ["10, 12", "$245"],
             ["14, 16", "$255"], ["18, 20", "$265"],
             ["28, 30", "$275"], ["32, 34", "$285"],
             ["36, 38", "$295"], ["40, 42, 44", "$315"]]),
         _s("Gales (Azul, Rojo, Verde)", ["Tallas", "Precio"],
            [["2, 4, 5, 6, 8", "$235"], ["10, 12, 14, 16", "$245"],
             ["18, 20, 28, 30", "$265"], ["32, 34", "$285"],
             ["36, 38, 40, 42", "$295"], ["44", "$315"]]),
         _s("Escocés", ["Tallas", "Precio"],
            [["2, 3, 4, 6, 8", "$199"], ["10, 12, 14, 16", "$235"],
             ["28, 30, 32", "$265"]]),
         _s("Gabardina Negro", ["Tallas", "Precio"],
            [["2 - 16", "$219"]]),
         _s("Vestir Mujer", ["Tallas", "Precio"],
            [["28 - 44", "$289"]]),
     ],
     "notes": ["Vestir incluye: Azul Marino, Negro, Caqui, Café, Blanco, Azul Rey, Verde, Verde olivo, Vino, Gris, Pata de gallo."]},

    # ── 9. Faldas ────────────────────────────────────────────────────────
    {"title": "Faldas", "tipo": "Falda", "cols": 4,
     "sections": [
         _s("Gales (Azul, Rojo, Verde)", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$195"], ["10, 12", "$205"],
             ["14, 16", "$215"], ["28 - 34", "$225"],
             ["36 - 42", "$235"], ["44", "$245"]]),
         _s("Vino", ["Tallas", "Precio"],
            [["4, 6, 8", "$199"], ["10, 12", "$205"],
             ["14, 16", "$215"], ["28 - 34", "$225"], ["36", "$235"]]),
         _s("Escocés", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$205"], ["10 - 16", "$215"],
             ["28 - 34", "$245"], ["36, 38", "$255"], ["40, 42", "$265"]]),
         _s("Gris (Claro y Obscuro)", ["Tallas", "Precio"],
            [["4 - 16", "$265"], ["28 - 34", "$275"],
             ["36, 38", "$285"], ["40, 42", "$295"]]),
         _s("Cuatro Tablas", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$195"], ["10 - 16", "$205"],
             ["28 - 34", "$225"], ["36 - 42", "$235"]]),
         _s("Escolar Azul Marino", ["Tallas", "Precio"],
            [["2 - 16", "$195"], ["18, 20, 28, 30", "$205"],
             ["32, 34", "$215"], ["36, 38", "$225"], ["40, 42", "$235"]]),
         _s("Pgallo Café", ["Tallas", "Precio"],
            [["12 - 16", "$205"], ["28 - 34", "$245"], ["36 - 42", "$255"]]),
         _s("Oficial Escolar", ["Tallas", "Precio"],
            [["12", "$205"], ["14, 16", "$215"],
             ["28 - 34", "$245"], ["36 - 42", "$255"]]),
     ],
     "exceptions": [
         _s("Excepciones por escuela", ["Escuela", "Tallas", "Precio"],
            [["Colegio Motolinea", "4-8/10-12/14-16/28-34/36-38",
              "205/215/225/245/255"],
             ["SABES", "10-16/28-34/36-38/40-42", "270/275/285/295"],
             ["Conalep", "14-16/28-34/36-42", "280/285/295"],
             ["Margarita Paz P.", "4, 6, 8 Preescolar", "$239"]]),
     ],
     "exc_cols": 1,
     "notes": ["Las faldas por escuela siempre deben estar por encima de la línea genérica."]},

    # ── 10. Jumper · Malla · Bata ────────────────────────────────────────
    {"title": "Jumper · Malla · Bata", "tipo": "Jumper", "cols": 3,
     "sections": [
         _s("Jumper", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$249"], ["10 - 16", "$269"],
             ["28, 30", "$289"], ["32, 34", "$309"],
             ["36, 38", "$319"], ["40, 42", "$329"]]),
         _s("Malla Escolar", ["Tallas", "Precio"],
            [["0-0, 0-2, 3-5, 6-8", "$109"], ["9-12", "$129"],
             ["13-18, CH-GD, Dama", "$139"]]),
         _s("Bata", ["Tipo / Tallas", "Precio"],
            [["Infantil (Uni)", "$65"], ["Manga Corta (12-46)", "$395"],
             ["Manga Larga (12-46)", "$439"]]),
     ],
     "notes": ["Si una pieza ya tiene precio mayor marcado, se respeta."]},

    # ── 11. Accesorios · Playera Polo ────────────────────────────────────
    {"title": "Accesorios · Playera Polo Blanca", "tipo": "Corbata", "cols": 2,
     "sections": [
         _s("Accesorios", ["Pieza", "Precio"],
            [["Calceta Escolar", "$49"], ["Guante Escolta", "$49"],
             ["Corbata", "$70"], ["Corbatín", "$70"],
             ["Moño", "$70"], ["Boina Escolta", "$80"]]),
         _s("Playera Polo Blanca", ["Tallas", "Precio"],
            [["2, 4, 6, 8", "$135"], ["10, 12", "$145"],
             ["14, 16, 18", "$155"], ["28 - 38", "$170"],
             ["40, 42", "$180"], ["CH, MD", "$185"], ["GD, EXG", "$195"]]),
     ],
     "notes": ["Si una pieza ya tiene precio mayor marcado, se respeta."]},
]


def _gen_sec_height(sec: dict) -> float:
    """Estimated mm height for a general-tarifario section."""
    return 6.5 + 5 + 5 * len(sec["rows"]) + 2.5


def _render_gen_section(pdf: TarifarioPDF, sec: dict,
                        x: float, y: float, col_w: float,
                        colors: tuple) -> float:
    """Render one section (header bar + table rows). Returns bottom y."""
    accent, bg, row_alt, title_clr, price_clr, line_clr = colors
    headers = sec["headers"]
    rows = sec["rows"]
    n = len(headers)

    # Column widths: first column wider
    first_w = col_w * (0.55 if n == 2 else 0.38)
    other_w = (col_w - first_w) / max(n - 1, 1)

    # ── Section header bar
    pdf.set_fill_color(*accent)
    pdf.rect(x, y, col_w, 6.5, "F")
    pdf.set_xy(x + 3, y + 0.8)
    pdf.set_font("Arial", "B", 8)
    pdf.set_text_color(*WHITE)
    pdf.cell(col_w - 6, 5, sec["title"], align="L")
    y += 6.5

    # ── Column headers
    col_hdr = tuple(min(255, c + 12) for c in bg)
    pdf.set_fill_color(*col_hdr)
    pdf.rect(x, y, col_w, 5, "F")
    pdf.set_xy(x + 3, y + 0.5)
    pdf.set_font("Arial", "B", 6.5)
    pdf.set_text_color(*title_clr)
    pdf.cell(first_w - 3, 4, headers[0], align="L")
    for hi in range(1, n):
        pdf.cell(other_w, 4, headers[hi], align="C")
    y += 5

    # ── Data rows
    for ri, row in enumerate(rows):
        fill = row_alt if ri % 2 == 0 else ROW_WHITE
        pdf.set_fill_color(*fill)
        pdf.rect(x, y, col_w, 5, "F")
        pdf.set_draw_color(*line_clr)
        pdf.line(x + 2, y, x + col_w - 2, y)

        pdf.set_xy(x + 3, y + 0.5)
        pdf.set_font("Arial", "", 7.5)
        pdf.set_text_color(*DARK_TEXT)
        pdf.cell(first_w - 3, 4, row[0], align="L")
        for ci in range(1, n):
            val = row[ci] if ci < len(row) else ""
            pdf.set_font("Arial", "B", 7.5)
            pdf.set_text_color(*price_clr)
            pdf.cell(other_w, 4, val, align="C")
        y += 5

    return y + 2.5


def _render_gen_grid(pdf: TarifarioPDF, sections: list[dict],
                     n_cols: int, page_w: float, colors: tuple):
    """Render sections in a grid (fills left→right, top→bottom)."""
    col_gap = 4
    col_w = (page_w - col_gap * (n_cols - 1)) / n_cols
    n_grid_rows = (len(sections) + n_cols - 1) // n_cols

    for ri in range(n_grid_rows):
        y_start = pdf.get_y()
        max_bottom = y_start
        for ci in range(n_cols):
            idx = ri * n_cols + ci
            if idx >= len(sections):
                break
            x = 10 + ci * (col_w + col_gap)
            bottom = _render_gen_section(pdf, sections[idx], x, y_start,
                                         col_w, colors)
            max_bottom = max(max_bottom, bottom)
        pdf.set_y(max_bottom)


def _render_gen_notes(pdf: TarifarioPDF, notes: list[str], page_w: float):
    """Render note lines at the current Y position."""
    y = pdf.get_y() + 1
    for note in notes:
        pdf.set_xy(12, y)
        pdf.set_font("Arial", "I", 7)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(page_w - 4, 4, f"  * {note}", align="L")
        y += 5
    pdf.set_y(y)


def render_general_pages(pdf: TarifarioPDF):
    """Render all general tarifario pages directly in the PDF."""
    # ── Divider page
    pdf.current_school = ""
    pdf.add_page()
    page_w = pdf.w - 20
    pdf.set_fill_color(*NAVY)
    pdf.rect(10, 55, page_w, 28, "F")
    pdf.set_xy(10, 58)
    pdf.set_font("Arial", "B", 24)
    pdf.set_text_color(*WHITE)
    pdf.cell(page_w, 12, "TARIFARIO GENERAL", align="C")
    pdf.set_xy(10, 72)
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(157, 195, 230)
    pdf.cell(page_w, 8, "Productos genéricos  ·  Precios de referencia", align="C")

    # ── Each page
    for pg in GENERAL_PAGES:
        pdf.current_school = pg["title"]
        pdf.add_page()
        page_w = pdf.w - 20

        tipo_colors = _colors_for(pg["tipo"])
        n_cols = pg.get("cols", 3)

        # Main sections
        _render_gen_grid(pdf, pg["sections"], n_cols, page_w, tipo_colors)

        # Exception sections (if any)
        exceptions = pg.get("exceptions")
        if exceptions:
            exc_cols = pg.get("exc_cols", n_cols)
            # Check if exceptions fit on current page
            exc_h = sum(_gen_sec_height(s) for s in exceptions)
            remaining = pdf.h - pdf.get_y() - 15
            if exc_h > remaining:
                pdf.add_page()
            _render_gen_grid(pdf, exceptions, exc_cols, page_w, _EXC_COLORS)

        # Notes
        notes = pg.get("notes")
        if notes:
            _render_gen_notes(pdf, notes, page_w)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    hoy = date.today()
    mes = MESES.get(hoy.month, str(hoy.month))
    updated = f"Actualizado: {mes} {hoy.year}"

    conn = psycopg.connect("dbname=pos_uniformes")
    print("Conectado a base de datos.")

    schools_data = fetch_schools_data(conn)
    print(f"Escuelas encontradas: {len(schools_data)}")

    conn.close()

    pdf = TarifarioPDF(updated_text=updated)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=False)

    # ── Portada ──────────────────────────────────────────────────────────────
    _render_cover(pdf, updated, hoy.year)

    # ── Índice (placeholder — se reescribe al final) ──────────────────────
    index_page = pdf.page_no() + 1  # next page will be the index
    _render_index_placeholder(pdf)

    # ── Páginas de escuelas ───────────────────────────────────────────────
    school_pages: list[tuple[str, int]] = []  # (nombre, página)

    for school_name, rows in schools_data.items():
        nivel_sections = group_school_products_by_nivel(rows)
        if not nivel_sections:
            continue
        school_pages.append((school_name, pdf.page_no() + 1))
        render_school_page(pdf, school_name, nivel_sections)
        total_rangos = sum(
            len(p["rangos"])
            for _, groups in nivel_sections
            for g in groups
            for p in g["productos"]
        )
        if len(nivel_sections) > 1:
            niveles = ", ".join(n for n, _ in nivel_sections)
            print(f"  ✓ {school_name} ({total_rangos} rangos) [{niveles}]")
        else:
            print(f"  ✓ {school_name} ({total_rangos} rangos)")

    # ── Reescribir índice con páginas reales ──────────────────────────────
    _rewrite_index(pdf, school_pages, index_page)

    n_escuelas = pdf.page_no()
    print(f"\n   Páginas escuelas: {n_escuelas}")

    # ── Tarifario General (productos genéricos) ──────────────────────────
    render_general_pages(pdf)
    n_general = pdf.page_no() - n_escuelas
    print(f"   Páginas tarifario general: {n_general}")

    # ── Guardar PDF final ────────────────────────────────────────────────
    out_path = OUTPUT_DIR / f"Tarifario_Escuelas_{hoy.year}.pdf"
    pdf.output(str(out_path))
    print(f"\n✅ PDF generado: {out_path}")
    print(f"   Total páginas: {pdf.page_no()}")


if __name__ == "__main__":
    main()
