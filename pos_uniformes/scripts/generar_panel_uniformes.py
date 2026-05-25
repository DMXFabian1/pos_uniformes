#!/usr/bin/env python3
"""Genera el panel HTML de gestión de uniformes por escuela.

Uso:
    python3 scripts/generar_panel_uniformes.py

Genera: pos_uniformes/panel_uniformes.html
"""

from __future__ import annotations

import os
import sys
from collections import OrderedDict
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg2

# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

def _get_connection():
    env_path = Path(__file__).resolve().parent.parent / "pos_uniformes.env"
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                env[k] = v
    return psycopg2.connect(
        host=env.get("POS_UNIFORMES_DB_HOST", "localhost"),
        port=int(env.get("POS_UNIFORMES_DB_PORT", "5432")),
        dbname=env.get("POS_UNIFORMES_DB_NAME", "pos_uniformes"),
        user=env.get("POS_UNIFORMES_DB_USER", "postgres"),
        password=env.get("POS_UNIFORMES_DB_PASSWORD", "1234"),
    )

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

NIVEL_ORDER = ["Preescolar", "Primaria", "Secundaria", "Bachillerato"]
PIEZA_ORDER = [
    "Pants 3pz", "Pants 2pz", "Pants Suelto", "Chamarra", "Playera",
    "Suéter", "Falda", "Camisa", "Chaleco", "Pantalón",
    "Corbata", "Corbatín", "Mascada",
]

TALLA_ORDER = [
    "2", "4", "6", "8", "10", "12", "14", "16", "18",
    "20", "22", "24", "26", "28", "30", "32", "34", "36", "38", "40", "42", "44",
    "XCH", "CH", "MD", "M", "GD", "G", "EXG", "XL", "2XL", "3XL",
    "U", "Unitalla",
]


def talla_sort_key(t: str) -> tuple:
    try:
        idx = TALLA_ORDER.index(t)
    except ValueError:
        idx = 999
    return (idx, t)


def fetch_all_data(conn):
    cur = conn.cursor()

    # 1. Stats
    cur.execute("""
        SELECT
            (SELECT COUNT(*) FROM escuela WHERE activo=true),
            (SELECT COUNT(*) FROM producto WHERE activo=true),
            (SELECT COUNT(*) FROM variante WHERE activo=true AND producto_id IN (SELECT id FROM producto WHERE activo=true)),
            (SELECT COUNT(*) FROM variante WHERE activo=false AND producto_id IN (SELECT id FROM producto WHERE activo=true))
    """)
    stats = dict(zip(["escuelas", "productos", "variantes_activas", "variantes_inactivas"], cur.fetchone()))

    # 2. Multi-level detection
    cur.execute("""
        SELECT p.escuela_id
        FROM producto p JOIN escuela e ON e.id=p.escuela_id AND e.activo=true
        WHERE p.activo=true
        GROUP BY p.escuela_id HAVING COUNT(DISTINCT p.nivel_educativo_id) > 1
    """)
    multi_level_ids = {r[0] for r in cur.fetchall()}

    # 3. Schools with levels
    cur.execute("""
        SELECT DISTINCT e.id, e.nombre, ne.id, ne.nombre
        FROM escuela e
        JOIN producto p ON p.escuela_id=e.id AND p.activo=true
        JOIN nivel_educativo ne ON ne.id=p.nivel_educativo_id
        WHERE e.activo=true
        ORDER BY ne.nombre, e.nombre
    """)
    school_levels = []
    for eid, ename, nid, nname in cur.fetchall():
        display = f"{ename} {nname}" if eid in multi_level_ids else ename
        school_levels.append({
            "escuela_id": eid, "escuela_nombre": ename,
            "nivel_id": nid, "nivel_nombre": nname,
            "display_name": display,
        })

    # 4. Pieces matrix
    cur.execute("""
        SELECT e.id, ne.nombre, tp.nombre, COUNT(DISTINCT p.id)
        FROM producto p
        JOIN escuela e ON e.id=p.escuela_id AND e.activo=true
        JOIN nivel_educativo ne ON ne.id=p.nivel_educativo_id
        JOIN tipo_pieza tp ON tp.id=p.tipo_pieza_id
        WHERE p.activo=true
        GROUP BY e.id, ne.nombre, tp.nombre
    """)
    pieces_raw = cur.fetchall()

    # 5. Full catalog (products + variants)
    cur.execute("""
        SELECT
            e.id AS escuela_id, e.nombre AS escuela,
            ne.nombre AS nivel, tp.nombre AS tipo_pieza,
            p.id AS producto_id, p.nombre_base,
            v.id AS variante_id, v.sku, v.talla, v.color,
            v.precio_venta, v.stock_actual, v.activo AS v_activo
        FROM producto p
        JOIN escuela e ON e.id=p.escuela_id AND e.activo=true
        JOIN nivel_educativo ne ON ne.id=p.nivel_educativo_id
        JOIN tipo_pieza tp ON tp.id=p.tipo_pieza_id
        LEFT JOIN variante v ON v.producto_id=p.id
        WHERE p.activo=true
        ORDER BY e.nombre, ne.nombre, tp.nombre, p.nombre_base, v.talla, v.color
    """)
    catalog_rows = cur.fetchall()
    catalog_cols = [d[0] for d in cur.description]

    cur.close()
    return stats, multi_level_ids, school_levels, pieces_raw, catalog_rows, catalog_cols


# ---------------------------------------------------------------------------
# Build sections
# ---------------------------------------------------------------------------

def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_stats_section(stats):
    return f"""
    <div class="stats-grid">
        <div class="stat-card"><div class="stat-number">{stats['escuelas']}</div><div class="stat-label">Escuelas activas</div></div>
        <div class="stat-card"><div class="stat-number">{stats['productos']}</div><div class="stat-label">Productos activos</div></div>
        <div class="stat-card"><div class="stat-number">{stats['variantes_activas']}</div><div class="stat-label">Variantes activas</div></div>
        <div class="stat-card accent"><div class="stat-number">{stats['variantes_inactivas']}</div><div class="stat-label">Variantes inactivas</div></div>
    </div>"""


def build_pieces_section(school_levels, pieces_raw, multi_level_ids):
    # Build lookup: (escuela_id, nivel, tipo) -> count
    pieces_map = {}
    for eid, nivel, tipo, cnt in pieces_raw:
        pieces_map[(eid, nivel, tipo)] = cnt

    all_tipos = [t for t in PIEZA_ORDER if any(r[2] == t for r in pieces_raw)]

    html = []
    # Group by nivel
    niveles = OrderedDict()
    for sl in school_levels:
        n = sl["nivel_nombre"]
        if n not in niveles:
            niveles[n] = []
        niveles[n].append(sl)

    # Sort by NIVEL_ORDER
    sorted_niveles = OrderedDict()
    for n in NIVEL_ORDER:
        if n in niveles:
            sorted_niveles[n] = niveles[n]

    for nivel, schools in sorted_niveles.items():
        html.append(f'<h3 class="nivel-header">{_esc(nivel)} <span class="badge">{len(schools)}</span></h3>')
        html.append('<div class="table-wrapper"><table class="matrix-table">')
        html.append('<thead><tr><th class="school-col">#</th><th class="school-col">Escuela</th>')
        for t in all_tipos:
            short = t.replace("Pants ", "P·").replace("Suelto", "S")
            html.append(f'<th class="piece-col" title="{_esc(t)}">{_esc(short)}</th>')
        html.append('</tr></thead><tbody>')
        for i, sl in enumerate(schools, 1):
            eid = sl["escuela_id"]
            html.append(f'<tr data-school="{_esc(sl["display_name"])}">')
            html.append(f'<td>{i}</td><td class="school-cell">{_esc(sl["display_name"])}</td>')
            for t in all_tipos:
                cnt = pieces_map.get((eid, nivel, t))
                if cnt:
                    extra = f' <span class="count-badge">{cnt}</span>' if cnt > 1 else ""
                    html.append(f'<td class="has">✓{extra}</td>')
                else:
                    html.append('<td class="miss">—</td>')
            html.append('</tr>')
        html.append('</tbody></table></div>')

    return "\n".join(html)


def build_catalog_section(catalog_rows, catalog_cols, multi_level_ids):
    """Full catalog grouped by school > product with variant detail."""
    # Group: escuela_id -> product_id -> [variants]
    from collections import defaultdict
    schools = OrderedDict()  # (eid, ename, nivel) -> products
    products = OrderedDict()  # product_id -> {info, variants}

    col_idx = {c: i for i, c in enumerate(catalog_cols)}

    for row in catalog_rows:
        eid = row[col_idx["escuela_id"]]
        ename = row[col_idx["escuela"]]
        nivel = row[col_idx["nivel"]]
        tipo = row[col_idx["tipo_pieza"]]
        pid = row[col_idx["producto_id"]]
        pname = row[col_idx["nombre_base"]]

        display = f"{ename} {nivel}" if eid in multi_level_ids else ename
        school_key = (eid, display, nivel)

        if school_key not in schools:
            schools[school_key] = OrderedDict()

        if pid not in schools[school_key]:
            schools[school_key][pid] = {
                "nombre": pname, "tipo": tipo, "nivel": nivel,
                "variants": [],
            }

        vid = row[col_idx["variante_id"]]
        if vid is not None:
            schools[school_key][pid]["variants"].append({
                "sku": row[col_idx["sku"]],
                "talla": row[col_idx["talla"]] or "-",
                "color": row[col_idx["color"]] or "-",
                "precio": row[col_idx["precio_venta"]],
                "stock": row[col_idx["stock_actual"]],
                "activo": row[col_idx["v_activo"]],
            })

    html = []
    html.append('<div class="catalog-controls">')
    html.append('<input type="text" id="catalogSearch" placeholder="Buscar escuela, producto, SKU..." class="search-input" oninput="filterCatalog()">')
    html.append('<select id="catalogNivel" class="filter-select" onchange="filterCatalog()"><option value="">Todos los niveles</option>')
    for n in NIVEL_ORDER:
        html.append(f'<option value="{n}">{n}</option>')
    html.append('</select></div>')

    for (eid, display, nivel), prods in schools.items():
        total_variants = sum(len(p["variants"]) for p in prods.values())
        active_variants = sum(sum(1 for v in p["variants"] if v["activo"]) for p in prods.values())
        inactive_variants = total_variants - active_variants

        html.append(f'<div class="school-block" data-school="{_esc(display)}" data-nivel="{_esc(nivel)}">')
        html.append(f'<div class="school-header" onclick="this.parentElement.classList.toggle(\'collapsed\')">')
        html.append(f'<span class="school-title">{_esc(display)}</span>')
        html.append(f'<span class="school-meta">{len(prods)} productos · {active_variants} variantes')
        if inactive_variants > 0:
            html.append(f' · <span class="inactive-badge">{inactive_variants} inactivas</span>')
        html.append(f'</span><span class="toggle-icon">▾</span></div>')
        html.append('<div class="school-body">')

        for pid, pdata in prods.items():
            if not pdata["variants"]:
                continue
            # Get unique prices, tallas, colors
            prices = sorted(set(float(v["precio"]) for v in pdata["variants"] if v["activo"] and v["precio"]))
            tallas = sorted(set(v["talla"] for v in pdata["variants"] if v["activo"]), key=talla_sort_key)
            colors = sorted(set(v["color"] for v in pdata["variants"] if v["activo"] and v["color"] != "Sin color"))
            total_stock = sum(v["stock"] or 0 for v in pdata["variants"] if v["activo"])

            price_str = f"${prices[0]:,.0f}" if len(prices) == 1 else f"${prices[0]:,.0f}–${prices[-1]:,.0f}" if prices else "—"
            talla_str = ", ".join(tallas) if tallas else "—"
            color_str = ", ".join(colors) if colors else "—"

            html.append(f'<div class="product-row" data-name="{_esc(pdata["nombre"])}">')
            html.append(f'<div class="product-name"><span class="tipo-badge">{_esc(pdata["tipo"])}</span> {_esc(pdata["nombre"])}</div>')
            html.append(f'<div class="product-meta">')
            html.append(f'<span title="Precio">{price_str}</span>')
            html.append(f'<span title="Tallas" class="tallas-chip">{_esc(talla_str)}</span>')
            if colors:
                html.append(f'<span title="Colores" class="colors-chip">{_esc(color_str)}</span>')
            html.append(f'<span title="Stock total" class="stock-chip">Stock: {total_stock}</span>')
            html.append(f'<span class="variants-count">{len([v for v in pdata["variants"] if v["activo"]])} var.</span>')
            html.append('</div></div>')

        html.append('</div></div>')

    return "\n".join(html)


def build_missing_section(school_levels, pieces_raw, multi_level_ids):
    """Detect missing pieces per school vs a base template per level."""
    # Base template: most common pieces per nivel
    pieces_by_nivel = {}
    for eid, nivel, tipo, cnt in pieces_raw:
        if nivel not in pieces_by_nivel:
            pieces_by_nivel[nivel] = {}
        if tipo not in pieces_by_nivel[nivel]:
            pieces_by_nivel[nivel][tipo] = 0
        pieces_by_nivel[nivel][tipo] += 1

    # Template = pieces that >50% of schools in that level have
    templates = {}
    nivel_school_counts = {}
    for sl in school_levels:
        n = sl["nivel_nombre"]
        nivel_school_counts[n] = nivel_school_counts.get(n, 0) + 1

    for nivel, tipos in pieces_by_nivel.items():
        total = nivel_school_counts.get(nivel, 1)
        templates[nivel] = [t for t, c in tipos.items() if c >= total * 0.5]

    # Build: (escuela_id, nivel) -> set of tipos
    school_pieces = {}
    for eid, nivel, tipo, cnt in pieces_raw:
        key = (eid, nivel)
        if key not in school_pieces:
            school_pieces[key] = set()
        school_pieces[key].add(tipo)

    html = []

    # Template legend
    html.append('<div class="template-legend">')
    html.append('<h4>Plantilla base por nivel (piezas que &gt;50% de escuelas tienen)</h4>')
    for nivel in NIVEL_ORDER:
        if nivel in templates:
            tipos = sorted(templates[nivel], key=lambda t: PIEZA_ORDER.index(t) if t in PIEZA_ORDER else 99)
            html.append(f'<div class="template-row"><strong>{nivel}:</strong> {", ".join(tipos)}</div>')
    html.append('</div>')

    # Missing per school
    has_missing = False
    sorted_niveles = OrderedDict()
    for sl in school_levels:
        n = sl["nivel_nombre"]
        if n not in sorted_niveles:
            sorted_niveles[n] = []
        sorted_niveles[n].append(sl)

    for nivel in NIVEL_ORDER:
        if nivel not in sorted_niveles:
            continue
        template = set(templates.get(nivel, []))
        if not template:
            continue

        missing_schools = []
        for sl in sorted_niveles[nivel]:
            school_tipos = school_pieces.get((sl["escuela_id"], nivel), set())
            missing = template - school_tipos
            if missing:
                missing_schools.append((sl["display_name"], sorted(missing, key=lambda t: PIEZA_ORDER.index(t) if t in PIEZA_ORDER else 99)))

        if missing_schools:
            has_missing = True
            html.append(f'<h3 class="nivel-header">{_esc(nivel)} <span class="badge warn">{len(missing_schools)} con faltantes</span></h3>')
            html.append('<div class="table-wrapper"><table class="missing-table">')
            html.append('<thead><tr><th>Escuela</th><th>Piezas faltantes</th><th>Tiene</th></tr></thead><tbody>')
            for sname, missing in missing_schools:
                school_has = school_pieces.get(
                    next((sl["escuela_id"], nivel) for sl in sorted_niveles[nivel] if sl["display_name"] == sname),
                    set(),
                )
                # Find the right key
                for sl in sorted_niveles[nivel]:
                    if sl["display_name"] == sname:
                        school_has = school_pieces.get((sl["escuela_id"], nivel), set())
                        break
                has_list = sorted(school_has, key=lambda t: PIEZA_ORDER.index(t) if t in PIEZA_ORDER else 99)
                missing_html = " ".join(f'<span class="missing-chip">{_esc(m)}</span>' for m in missing)
                has_html = ", ".join(has_list)
                html.append(f'<tr><td class="school-cell">{_esc(sname)}</td><td>{missing_html}</td><td class="has-cell">{_esc(has_html)}</td></tr>')
            html.append('</tbody></table></div>')

    if not has_missing:
        html.append('<p class="all-good">Todas las escuelas tienen las piezas base de su nivel.</p>')

    return "\n".join(html)


def build_variants_section(catalog_rows, catalog_cols, multi_level_ids):
    """Summary: products with variant counts, colors, tallas, price ranges."""
    col_idx = {c: i for i, c in enumerate(catalog_cols)}
    from collections import defaultdict

    # Group by product
    products = OrderedDict()
    for row in catalog_rows:
        pid = row[col_idx["producto_id"]]
        if pid not in products:
            eid = row[col_idx["escuela_id"]]
            ename = row[col_idx["escuela"]]
            nivel = row[col_idx["nivel"]]
            display = f"{ename} {nivel}" if eid in multi_level_ids else ename
            products[pid] = {
                "nombre": row[col_idx["nombre_base"]],
                "escuela": display,
                "nivel": nivel,
                "tipo": row[col_idx["tipo_pieza"]],
                "activas": 0, "inactivas": 0,
                "tallas": set(), "colores": set(),
                "precios": set(), "stock_total": 0,
            }
        vid = row[col_idx["variante_id"]]
        if vid is None:
            continue
        p = products[pid]
        activo = row[col_idx["v_activo"]]
        if activo:
            p["activas"] += 1
            t = row[col_idx["talla"]] or "-"
            c = row[col_idx["color"]] or "-"
            if t != "-":
                p["tallas"].add(t)
            if c not in ("-", "Sin color"):
                p["colores"].add(c)
            precio = row[col_idx["precio_venta"]]
            if precio:
                p["precios"].add(float(precio))
            p["stock_total"] += row[col_idx["stock_actual"]] or 0
        else:
            p["inactivas"] += 1

    # Find problems
    html = []
    html.append('<div class="catalog-controls">')
    html.append('<input type="text" id="variantSearch" placeholder="Buscar producto, escuela..." class="search-input" oninput="filterVariants()">')
    html.append('<select id="variantFilter" class="filter-select" onchange="filterVariants()">')
    html.append('<option value="">Todos</option>')
    html.append('<option value="few">Pocas variantes (≤2)</option>')
    html.append('<option value="inactive">Con inactivas</option>')
    html.append('<option value="nostock">Sin stock</option>')
    html.append('<option value="multicolor">Multi-color</option>')
    html.append('</select></div>')

    html.append('<div class="table-wrapper"><table class="variant-table" id="variantTable">')
    html.append('<thead><tr>')
    html.append('<th>Escuela</th><th>Producto</th><th>Tipo</th>')
    html.append('<th>Act.</th><th>Inact.</th>')
    html.append('<th>Tallas</th><th>Colores</th><th>Precio</th><th>Stock</th>')
    html.append('</tr></thead><tbody>')

    for pid, p in products.items():
        prices = sorted(p["precios"])
        tallas = sorted(p["tallas"], key=talla_sort_key)
        colores = sorted(p["colores"])
        price_str = f"${prices[0]:,.0f}" if len(prices) == 1 else f"${prices[0]:,.0f}–${prices[-1]:,.0f}" if prices else "—"

        row_class = ""
        if p["activas"] <= 2:
            row_class = "few-variants"
        if p["inactivas"] > 0:
            row_class += " has-inactive"
        if p["stock_total"] == 0:
            row_class += " no-stock"
        if len(colores) > 1:
            row_class += " multi-color"

        html.append(f'<tr class="{row_class.strip()}" data-school="{_esc(p["escuela"])}" data-name="{_esc(p["nombre"])}">')
        html.append(f'<td class="school-cell">{_esc(p["escuela"])}</td>')
        html.append(f'<td>{_esc(p["nombre"])}</td>')
        html.append(f'<td><span class="tipo-badge sm">{_esc(p["tipo"])}</span></td>')
        html.append(f'<td class="num">{p["activas"]}</td>')
        inact_cls = "warn-text" if p["inactivas"] > 0 else ""
        html.append(f'<td class="num {inact_cls}">{p["inactivas"]}</td>')
        html.append(f'<td class="tallas-cell">{_esc(", ".join(tallas))}</td>')
        html.append(f'<td>{_esc(", ".join(colores)) if colores else "—"}</td>')
        html.append(f'<td class="num">{price_str}</td>')
        stock_cls = "warn-text" if p["stock_total"] == 0 else ""
        html.append(f'<td class="num {stock_cls}">{p["stock_total"]}</td>')
        html.append('</tr>')

    html.append('</tbody></table></div>')
    return "\n".join(html)


def build_tariff_section(catalog_rows, catalog_cols, multi_level_ids):
    """Compact tariff view per school: product -> talla -> price."""
    col_idx = {c: i for i, c in enumerate(catalog_cols)}

    # Group: school_display -> [{product, tallas: {talla: price}}]
    schools = OrderedDict()
    for row in catalog_rows:
        eid = row[col_idx["escuela_id"]]
        ename = row[col_idx["escuela"]]
        nivel = row[col_idx["nivel"]]
        display = f"{ename} {nivel}" if eid in multi_level_ids else ename
        pid = row[col_idx["producto_id"]]
        pname = row[col_idx["nombre_base"]]
        tipo = row[col_idx["tipo_pieza"]]

        if display not in schools:
            schools[display] = {"nivel": nivel, "products": OrderedDict()}
        if pid not in schools[display]["products"]:
            schools[display]["products"][pid] = {
                "nombre": pname, "tipo": tipo,
                "tallas": OrderedDict(),
            }
        vid = row[col_idx["variante_id"]]
        if vid is None or not row[col_idx["v_activo"]]:
            continue
        talla = row[col_idx["talla"]] or "-"
        precio = row[col_idx["precio_venta"]]
        color = row[col_idx["color"]] or "Sin color"
        # Use (talla, color) as key to handle multi-color
        schools[display]["products"][pid]["tallas"][(talla, color)] = float(precio) if precio else 0

    html = []
    html.append('<div class="catalog-controls">')
    html.append('<input type="text" id="tariffSearch" placeholder="Buscar escuela..." class="search-input" oninput="filterTariffs()">')
    html.append('</div>')

    for school_name, sdata in schools.items():
        prods = sdata["products"]
        html.append(f'<div class="tariff-block" data-school="{_esc(school_name)}">')
        html.append(f'<div class="school-header" onclick="this.parentElement.classList.toggle(\'collapsed\')">')
        html.append(f'<span class="school-title">{_esc(school_name)}</span>')
        html.append(f'<span class="school-meta">{len(prods)} productos</span>')
        html.append(f'<span class="toggle-icon">▾</span></div>')
        html.append('<div class="school-body">')

        for pid, pdata in prods.items():
            if not pdata["tallas"]:
                continue
            # Get unique tallas sorted
            all_tallas = sorted(set(t for t, c in pdata["tallas"].keys()), key=talla_sort_key)
            # Check if single color or multi
            unique_colors = set(c for t, c in pdata["tallas"].keys())
            single_color = len(unique_colors) <= 1

            html.append(f'<div class="tariff-product">')
            html.append(f'<span class="tipo-badge sm">{_esc(pdata["tipo"])}</span> <strong>{_esc(pdata["nombre"])}</strong>')

            if single_color:
                # Simple: talla -> price inline
                prices = {}
                for (t, c), p in pdata["tallas"].items():
                    prices[t] = p
                # Group by price
                price_groups = OrderedDict()
                for t in all_tallas:
                    p = prices.get(t, 0)
                    if p not in price_groups:
                        price_groups[p] = []
                    price_groups[p].append(t)

                parts = []
                for price, tallas in price_groups.items():
                    if len(tallas) > 2:
                        trange = f"{tallas[0]}–{tallas[-1]}"
                    else:
                        trange = ", ".join(tallas)
                    parts.append(f'<span class="tariff-chip">{trange}: <strong>${price:,.0f}</strong></span>')
                html.append(f'<div class="tariff-prices">{" ".join(parts)}</div>')
            else:
                # Multi-color: group by color
                by_color = OrderedDict()
                for (t, c), p in pdata["tallas"].items():
                    if c not in by_color:
                        by_color[c] = {}
                    by_color[c][t] = p
                for color, tprices in by_color.items():
                    sorted_t = sorted(tprices.keys(), key=talla_sort_key)
                    price_groups = OrderedDict()
                    for t in sorted_t:
                        p = tprices[t]
                        if p not in price_groups:
                            price_groups[p] = []
                        price_groups[p].append(t)
                    parts = []
                    for price, tallas in price_groups.items():
                        trange = f"{tallas[0]}–{tallas[-1]}" if len(tallas) > 2 else ", ".join(tallas)
                        parts.append(f'{trange}: <strong>${price:,.0f}</strong>')
                    html.append(f'<div class="tariff-color"><span class="color-name">{_esc(color)}</span> {" · ".join(parts)}</div>')

            html.append('</div>')

        html.append('</div></div>')

    return "\n".join(html)


# ---------------------------------------------------------------------------
# Main HTML template
# ---------------------------------------------------------------------------

def generate_html(stats, pieces_html, catalog_html, missing_html, variants_html, tariff_html):
    today = date.today()
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Panel de Uniformes — MAXIMODA</title>
<style>
:root {{
    --brand: #87492c;
    --brand-light: #f5ebe0;
    --brand-dark: #5c3019;
    --green: #2e7d32;
    --red: #c62828;
    --orange: #e65100;
    --gray: #666;
    --light-gray: #f5f5f5;
    --border: #ddd;
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 13px; color: #222; background: #faf8f6; }}

/* Header */
.header {{ background: var(--brand); color: white; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
.header h1 {{ font-size: 20px; font-weight: 700; }}
.header .date {{ font-size: 12px; opacity: 0.8; }}

/* Tabs */
.tabs {{ display: flex; background: white; border-bottom: 2px solid var(--border); padding: 0 16px; position: sticky; top: 52px; z-index: 99; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
.tab {{ padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; font-weight: 600; color: var(--gray); transition: all 0.2s; font-size: 13px; }}
.tab:hover {{ color: var(--brand); background: var(--brand-light); }}
.tab.active {{ color: var(--brand); border-bottom-color: var(--brand); }}

/* Content */
.content {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

/* Stats */
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }}
.stat-card {{ background: white; border-radius: 10px; padding: 16px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.08); border-left: 4px solid var(--brand); }}
.stat-card.accent {{ border-left-color: var(--orange); }}
.stat-number {{ font-size: 28px; font-weight: 700; color: var(--brand); }}
.stat-card.accent .stat-number {{ color: var(--orange); }}
.stat-label {{ font-size: 12px; color: var(--gray); margin-top: 4px; }}

/* Tables */
.table-wrapper {{ overflow-x: auto; margin-bottom: 16px; }}
table {{ border-collapse: collapse; width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
th {{ background: var(--brand); color: white; font-size: 11px; padding: 8px 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
td {{ padding: 6px 8px; border-bottom: 1px solid #eee; font-size: 12px; }}
tbody tr:hover {{ background: #fff8f0; }}
.school-col {{ text-align: left; min-width: 180px; }}
.school-cell {{ text-align: left; font-weight: 600; white-space: nowrap; }}
.piece-col {{ width: 50px; }}
.has {{ color: var(--green); font-weight: bold; font-size: 14px; text-align: center; }}
.miss {{ color: #ddd; text-align: center; }}
.count-badge {{ font-size: 9px; color: var(--gray); }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.warn-text {{ color: var(--red); font-weight: 600; }}
.tallas-cell {{ font-size: 11px; max-width: 200px; }}
.has-cell {{ font-size: 11px; color: var(--gray); }}

/* Nivel headers */
.nivel-header {{ font-size: 15px; color: var(--brand); border-bottom: 2px solid var(--brand); padding: 8px 0 4px; margin: 20px 0 10px; }}
.nivel-header:first-child {{ margin-top: 0; }}
.badge {{ background: var(--brand); color: white; font-size: 11px; padding: 2px 10px; border-radius: 10px; margin-left: 8px; font-weight: normal; }}
.badge.warn {{ background: var(--orange); }}

/* Search/Filter controls */
.catalog-controls {{ display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }}
.search-input {{ flex: 1; min-width: 200px; padding: 8px 14px; border: 2px solid var(--border); border-radius: 8px; font-size: 13px; outline: none; transition: border-color 0.2s; }}
.search-input:focus {{ border-color: var(--brand); }}
.filter-select {{ padding: 8px 14px; border: 2px solid var(--border); border-radius: 8px; font-size: 13px; background: white; cursor: pointer; }}

/* Collapsible school blocks */
.school-block, .tariff-block {{ background: white; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); overflow: hidden; }}
.school-header {{ display: flex; align-items: center; padding: 12px 16px; cursor: pointer; transition: background 0.2s; }}
.school-header:hover {{ background: var(--brand-light); }}
.school-title {{ font-weight: 700; font-size: 14px; flex: 1; }}
.school-meta {{ font-size: 11px; color: var(--gray); margin-right: 12px; }}
.toggle-icon {{ font-size: 16px; color: var(--gray); transition: transform 0.2s; }}
.collapsed .toggle-icon {{ transform: rotate(-90deg); }}
.collapsed .school-body {{ display: none; }}
.school-body {{ padding: 0 16px 12px; }}
.inactive-badge {{ color: var(--orange); font-weight: 600; }}

/* Product rows in catalog */
.product-row {{ display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; border-bottom: 1px solid #f0f0f0; flex-wrap: wrap; gap: 4px; }}
.product-row:last-child {{ border-bottom: none; }}
.product-row:hover {{ background: #faf5ef; }}
.product-name {{ font-weight: 600; font-size: 12px; flex: 1; min-width: 200px; }}
.product-meta {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 11px; color: var(--gray); }}
.tipo-badge {{ background: var(--brand-light); color: var(--brand); padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; }}
.tipo-badge.sm {{ font-size: 9px; padding: 1px 6px; }}
.tallas-chip {{ background: #e8f5e9; color: var(--green); padding: 1px 6px; border-radius: 4px; font-size: 10px; }}
.colors-chip {{ background: #e3f2fd; color: #1565c0; padding: 1px 6px; border-radius: 4px; font-size: 10px; }}
.stock-chip {{ font-weight: 600; }}
.variants-count {{ color: var(--brand); font-weight: 600; }}

/* Missing section */
.missing-table th {{ text-align: left; }}
.missing-chip {{ background: #ffebee; color: var(--red); padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; display: inline-block; margin: 2px; }}
.template-legend {{ background: white; border-radius: 10px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
.template-legend h4 {{ margin-bottom: 8px; color: var(--brand); }}
.template-row {{ font-size: 12px; padding: 2px 0; }}
.all-good {{ text-align: center; padding: 40px; color: var(--green); font-size: 16px; font-weight: 600; }}

/* Tariff section */
.tariff-product {{ padding: 6px 8px; border-bottom: 1px solid #f0f0f0; font-size: 12px; }}
.tariff-product:last-child {{ border-bottom: none; }}
.tariff-prices {{ margin-top: 4px; display: flex; gap: 6px; flex-wrap: wrap; }}
.tariff-chip {{ background: var(--light-gray); padding: 2px 8px; border-radius: 4px; font-size: 11px; }}
.tariff-color {{ margin-top: 2px; font-size: 11px; padding-left: 12px; }}
.color-name {{ font-weight: 600; color: var(--brand); }}

/* Variant table highlights */
.few-variants td:nth-child(4) {{ background: #fff3e0; }}
.has-inactive td:nth-child(5) {{ background: #ffebee; }}
.no-stock td:nth-child(9) {{ background: #ffebee; }}

/* Print */
@media print {{
    .header {{ position: static; }}
    .tabs {{ display: none; }}
    .tab-content {{ display: block !important; page-break-before: always; }}
    .tab-content:first-child {{ page-break-before: auto; }}
    .search-input, .filter-select, .catalog-controls {{ display: none; }}
    .school-block, .tariff-block {{ break-inside: avoid; }}
    .collapsed .school-body {{ display: block !important; }}
    th {{ position: static; }}
}}
</style>
</head>
<body>

<div class="header">
    <h1>MAXIMODA — Panel de Uniformes</h1>
    <div class="date">Generado: {today}</div>
</div>

<div class="tabs">
    <div class="tab active" onclick="showTab('resumen')">Resumen</div>
    <div class="tab" onclick="showTab('piezas')">Piezas por Escuela</div>
    <div class="tab" onclick="showTab('tarifarios')">Tarifarios</div>
    <div class="tab" onclick="showTab('catalogo')">Catálogo</div>
    <div class="tab" onclick="showTab('faltantes')">Faltantes</div>
    <div class="tab" onclick="showTab('variantes')">Variantes</div>
</div>

<div class="content">
    <div id="resumen" class="tab-content active">
        <h2 style="margin-bottom:16px;">Resumen General</h2>
        {stats}
    </div>

    <div id="piezas" class="tab-content">
        <h2 style="margin-bottom:16px;">Piezas por Escuela</h2>
        {pieces_html}
    </div>

    <div id="tarifarios" class="tab-content">
        <h2 style="margin-bottom:16px;">Tarifarios por Escuela</h2>
        {tariff_html}
    </div>

    <div id="catalogo" class="tab-content">
        <h2 style="margin-bottom:16px;">Catálogo por Escuela</h2>
        {catalog_html}
    </div>

    <div id="faltantes" class="tab-content">
        <h2 style="margin-bottom:16px;">Piezas Faltantes</h2>
        {missing_html}
    </div>

    <div id="variantes" class="tab-content">
        <h2 style="margin-bottom:16px;">Resumen de Variantes</h2>
        {variants_html}
    </div>
</div>

<script>
function showTab(id) {{
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    // Find the tab button
    const tabs = document.querySelectorAll('.tab');
    const names = ['resumen','piezas','tarifarios','catalogo','faltantes','variantes'];
    const idx = names.indexOf(id);
    if (idx >= 0) tabs[idx].classList.add('active');
}}

function filterCatalog() {{
    const q = document.getElementById('catalogSearch').value.toLowerCase();
    const nivel = document.getElementById('catalogNivel').value;
    document.querySelectorAll('.school-block').forEach(block => {{
        const school = block.dataset.school.toLowerCase();
        const blockNivel = block.dataset.nivel;
        const products = block.querySelectorAll('.product-row');
        let anyMatch = false;
        products.forEach(row => {{
            const name = row.dataset.name.toLowerCase();
            const match = (school.includes(q) || name.includes(q)) && (!nivel || blockNivel === nivel);
            row.style.display = match ? '' : 'none';
            if (match) anyMatch = true;
        }});
        const schoolMatch = school.includes(q) && (!nivel || blockNivel === nivel);
        block.style.display = (schoolMatch || anyMatch) ? '' : 'none';
        if (anyMatch && !schoolMatch) {{
            block.classList.remove('collapsed');
        }}
    }});
}}

function filterTariffs() {{
    const q = document.getElementById('tariffSearch').value.toLowerCase();
    document.querySelectorAll('.tariff-block').forEach(block => {{
        block.style.display = block.dataset.school.toLowerCase().includes(q) ? '' : 'none';
    }});
}}

function filterVariants() {{
    const q = document.getElementById('variantSearch').value.toLowerCase();
    const f = document.getElementById('variantFilter').value;
    document.querySelectorAll('#variantTable tbody tr').forEach(row => {{
        const school = (row.dataset.school || '').toLowerCase();
        const name = (row.dataset.name || '').toLowerCase();
        let textMatch = school.includes(q) || name.includes(q);
        let filterMatch = true;
        if (f === 'few') filterMatch = row.classList.contains('few-variants');
        if (f === 'inactive') filterMatch = row.classList.contains('has-inactive');
        if (f === 'nostock') filterMatch = row.classList.contains('no-stock');
        if (f === 'multicolor') filterMatch = row.classList.contains('multi-color');
        row.style.display = (textMatch && filterMatch) ? '' : 'none';
    }});
}}

// Start with all school blocks collapsed except first
document.addEventListener('DOMContentLoaded', () => {{
    document.querySelectorAll('.school-block, .tariff-block').forEach((block, i) => {{
        if (i > 0) block.classList.add('collapsed');
    }});
}});
</script>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Conectando a la base de datos...")
    conn = _get_connection()
    print("Consultando datos...")
    stats, multi_level_ids, school_levels, pieces_raw, catalog_rows, catalog_cols = fetch_all_data(conn)
    conn.close()

    print(f"  {stats['escuelas']} escuelas, {stats['productos']} productos, {stats['variantes_activas']} variantes")

    print("Generando secciones...")
    stats_html = build_stats_section(stats)
    pieces_html = build_pieces_section(school_levels, pieces_raw, multi_level_ids)
    catalog_html = build_catalog_section(catalog_rows, catalog_cols, multi_level_ids)
    missing_html = build_missing_section(school_levels, pieces_raw, multi_level_ids)
    variants_html = build_variants_section(catalog_rows, catalog_cols, multi_level_ids)
    tariff_html = build_tariff_section(catalog_rows, catalog_cols, multi_level_ids)

    html = generate_html(stats_html, pieces_html, catalog_html, missing_html, variants_html, tariff_html)

    out_path = Path(__file__).resolve().parent.parent / "panel_uniformes.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Panel generado: {out_path}")
    print(f"  Abre: file://{out_path}")


if __name__ == "__main__":
    main()
