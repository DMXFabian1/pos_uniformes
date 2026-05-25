#!/usr/bin/env python3
"""Genera el panel HTML de gestión de uniformes por escuela.

Uso:
    python3 scripts/generar_panel_uniformes.py

Genera: pos_uniformes/panel_uniformes.html
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Conexión  (usa el engine de SQLAlchemy — no requiere psycopg2 directo)
# ---------------------------------------------------------------------------

def _get_connection():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from pos_uniformes.database.connection import engine  # noqa: PLC0415
    return engine.raw_connection()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NIVEL_ORDER = ["Preescolar", "Primaria", "Secundaria", "Bachillerato"]
NIVEL_COLORS = {
    "Preescolar": "#7c4dff",
    "Primaria": "#2979ff",
    "Secundaria": "#00bfa5",
    "Bachillerato": "#ff6d00",
}
PIEZA_ORDER = [
    "Pants 3pz", "Pants 2pz", "Pants Suelto", "Chamarra", "Playera",
    "Suéter", "Camisa", "Chaleco", "Falda", "Pantalón",
    "Corbata", "Corbatín", "Moño", "Mascada",
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

def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def compute_default_na(school_levels, pieces_raw):
    """Generate default NA marks for pieces that schools are known not to carry."""
    na = {}

    primaria_eids = {sl["escuela_id"] for sl in school_levels if sl["nivel_nombre"] == "Primaria"}
    secundaria_eids = {sl["escuela_id"] for sl in school_levels if sl["nivel_nombre"] == "Secundaria"}
    bachillerato_eids = {sl["escuela_id"] for sl in school_levels if sl["nivel_nombre"] == "Bachillerato"}

    has_piece = set()
    for eid, nivel, tipo, cnt in pieces_raw:
        if cnt:
            has_piece.add((eid, nivel, tipo))

    for eid in primaria_eids:
        for tipo in ["Corbata", "Corbatín", "Moño"]:
            if (eid, "Primaria", tipo) not in has_piece:
                na[f"{eid}_Primaria_{tipo}"] = True

    for eid in secundaria_eids:
        for tipo in ["Corbatín", "Moño"]:
            if (eid, "Secundaria", tipo) not in has_piece:
                na[f"{eid}_Secundaria_{tipo}"] = True

    # Bachillerato: each school carries exactly the piece types it needs;
    # anything missing is truly not applicable (not a gap to fill).
    for eid in bachillerato_eids:
        for tipo in PIEZA_ORDER:
            if (eid, "Bachillerato", tipo) not in has_piece:
                na[f"{eid}_Bachillerato_{tipo}"] = True

    return na


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_all_data(conn):
    cur = conn.cursor()

    # Stats
    cur.execute("""
        SELECT
            (SELECT COUNT(*) FROM escuela WHERE activo=true),
            (SELECT COUNT(*) FROM producto WHERE activo=true),
            (SELECT COUNT(*) FROM variante WHERE activo=true AND producto_id IN (SELECT id FROM producto WHERE activo=true)),
            (SELECT COUNT(*) FROM variante WHERE activo=false AND producto_id IN (SELECT id FROM producto WHERE activo=true))
    """)
    stats = dict(zip(["escuelas", "productos", "variantes_activas", "variantes_inactivas"], cur.fetchone()))

    # Schools per nivel
    cur.execute("""
        SELECT ne.nombre, COUNT(DISTINCT p.escuela_id)
        FROM producto p
        JOIN escuela e ON e.id=p.escuela_id AND e.activo=true
        JOIN nivel_educativo ne ON ne.id=p.nivel_educativo_id
        WHERE p.activo=true
        GROUP BY ne.nombre
    """)
    stats["por_nivel"] = dict(cur.fetchall())

    # Multi-level detection
    cur.execute("""
        SELECT p.escuela_id
        FROM producto p JOIN escuela e ON e.id=p.escuela_id AND e.activo=true
        WHERE p.activo=true
        GROUP BY p.escuela_id HAVING COUNT(DISTINCT p.nivel_educativo_id) > 1
    """)
    multi_level_ids = {r[0] for r in cur.fetchall()}

    # Schools with levels
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

    # Pieces matrix (direct + linked basic products)
    cur.execute("""
        WITH school_products AS (
            SELECT p.escuela_id, p.id AS producto_id, p.nivel_educativo_id, p.tipo_pieza_id
            FROM producto p WHERE p.activo=true AND p.escuela_id IS NOT NULL
            UNION
            SELECT l.escuela_id, p.id, ne_esc.nivel_educativo_id, p.tipo_pieza_id
            FROM catalog_school_product_link l
            JOIN producto p ON p.id=l.producto_id AND p.activo=true
            JOIN (SELECT DISTINCT p2.escuela_id, p2.nivel_educativo_id
                  FROM producto p2 WHERE p2.activo=true AND p2.escuela_id IS NOT NULL) ne_esc
                ON ne_esc.escuela_id=l.escuela_id
            WHERE l.activo=true
        )
        SELECT e.id, ne.nombre, tp.nombre, COUNT(DISTINCT sp.producto_id)
        FROM school_products sp
        JOIN escuela e ON e.id=sp.escuela_id AND e.activo=true
        JOIN nivel_educativo ne ON ne.id=sp.nivel_educativo_id
        JOIN tipo_pieza tp ON tp.id=sp.tipo_pieza_id
        GROUP BY e.id, ne.nombre, tp.nombre
    """)
    pieces_raw = cur.fetchall()

    # Full catalog (direct + linked basic products)
    cur.execute("""
        WITH all_school_products AS (
            SELECT p.escuela_id, p.id AS producto_id, p.nivel_educativo_id
            FROM producto p WHERE p.activo=true AND p.escuela_id IS NOT NULL
            UNION
            SELECT l.escuela_id, p.id, ne_esc.nivel_educativo_id
            FROM catalog_school_product_link l
            JOIN producto p ON p.id=l.producto_id AND p.activo=true
            JOIN (SELECT DISTINCT p2.escuela_id, p2.nivel_educativo_id
                  FROM producto p2 WHERE p2.activo=true AND p2.escuela_id IS NOT NULL) ne_esc
                ON ne_esc.escuela_id=l.escuela_id
            WHERE l.activo=true
        )
        SELECT
            e.id AS escuela_id, e.nombre AS escuela,
            ne.nombre AS nivel, tp.nombre AS tipo_pieza,
            p.id AS producto_id, p.nombre_base,
            v.id AS variante_id, v.sku, v.talla, v.color,
            v.precio_venta, v.stock_actual, v.activo AS v_activo
        FROM all_school_products asp
        JOIN escuela e ON e.id=asp.escuela_id AND e.activo=true
        JOIN producto p ON p.id=asp.producto_id
        JOIN nivel_educativo ne ON ne.id=asp.nivel_educativo_id
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
# Compute derived data
# ---------------------------------------------------------------------------

def compute_insights(stats, school_levels, pieces_raw, catalog_rows, catalog_cols, multi_level_ids):
    """Generate automatic insights for the resumen tab."""
    col_idx = {c: i for i, c in enumerate(catalog_cols)}
    insights = []

    # Pieces per school
    pieces_map = defaultdict(set)
    for eid, nivel, tipo, cnt in pieces_raw:
        pieces_map[(eid, nivel)].add(tipo)

    # Máximo de tipos por nivel (peer comparison).
    # Comparar cada escuela contra la más completa de su mismo nivel evita
    # penalizar escuelas que no manejan piezas específicas de otro nivel
    # (p.ej. CBTIS no necesita Corbatín ni Moño aunque existan en Bachillerato).
    max_tipos_por_nivel: dict[str, int] = defaultdict(int)
    for (eid, nivel), tipos in pieces_map.items():
        max_tipos_por_nivel[nivel] = max(max_tipos_por_nivel[nivel], len(tipos))

    # Coverage
    coverage_data = []
    for sl in school_levels:
        key = (sl["escuela_id"], sl["nivel_nombre"])
        nivel = sl["nivel_nombre"]
        has = len(pieces_map.get(key, set()))
        nivel_max = max_tipos_por_nivel.get(nivel, 1)
        pct = min(100, round(has / nivel_max * 100)) if nivel_max else 0
        coverage_data.append({"eid": sl["escuela_id"], "name": sl["display_name"], "nivel": nivel, "has": has, "total": nivel_max, "pct": pct})

    low_coverage = [c for c in coverage_data if c["pct"] < 40]
    full_coverage = [c for c in coverage_data if c["pct"] >= 80]

    if low_coverage:
        names = ", ".join(c["name"] for c in sorted(low_coverage, key=lambda x: x["pct"])[:4])
        insights.append(("warn", f"{len(low_coverage)} escuelas con menos del 40% de piezas base", names))
    insights.append(("ok", f"{len(full_coverage)} de {len(coverage_data)} escuelas con cobertura ≥80%", ""))

    # Stock analysis
    stock_by_product = defaultdict(lambda: {"stock": 0, "variants": 0, "name": "", "school": ""})
    zero_stock_products = 0
    total_products = 0
    for row in catalog_rows:
        pid = row[col_idx["producto_id"]]
        vid = row[col_idx["variante_id"]]
        if vid is None:
            continue
        if not row[col_idx["v_activo"]]:
            continue
        eid = row[col_idx["escuela_id"]]
        ename = row[col_idx["escuela"]]
        nivel = row[col_idx["nivel"]]
        display = f"{ename} {nivel}" if eid in multi_level_ids else ename
        p = stock_by_product[pid]
        p["stock"] += row[col_idx["stock_actual"]] or 0
        p["variants"] += 1
        p["name"] = row[col_idx["nombre_base"]]
        p["school"] = display

    for pid, p in stock_by_product.items():
        total_products += 1
        if p["stock"] == 0:
            zero_stock_products += 1

    if zero_stock_products > 0:
        pct = round(zero_stock_products / total_products * 100)
        insights.append(("alert", f"{zero_stock_products} productos sin stock ({pct}%)", "Revisar en la pestaña Variantes con filtro 'Sin stock'"))

    # Top schools by variants
    variants_by_school = defaultdict(int)
    for row in catalog_rows:
        if row[col_idx["variante_id"]] and row[col_idx["v_activo"]]:
            eid = row[col_idx["escuela_id"]]
            ename = row[col_idx["escuela"]]
            nivel = row[col_idx["nivel"]]
            display = f"{ename} {nivel}" if eid in multi_level_ids else ename
            variants_by_school[display] += 1
    top_3 = sorted(variants_by_school.items(), key=lambda x: -x[1])[:3]
    if top_3:
        detail = " · ".join(f"{n} ({c})" for n, c in top_3)
        insights.append(("info", "Escuelas con más variantes", detail))

    return insights, coverage_data


# ---------------------------------------------------------------------------
# HTML Section builders
# ---------------------------------------------------------------------------

def build_resumen(stats, insights, coverage_data):
    niveles = stats["por_nivel"]
    total = stats["escuelas"]
    h = []

    # KPI cards row
    h.append('<div class="kpi-row">')
    kpis = [
        (stats["escuelas"], "Escuelas", "school", ""),
        (stats["productos"], "Productos", "product", "activos"),
        (stats["variantes_activas"], "Variantes", "variant", "activas"),
        (stats["variantes_inactivas"], "Inactivas", "inactive", "variantes"),
    ]
    for val, label, cls, sub in kpis:
        h.append(f'<div class="kpi-card {cls}"><div class="kpi-value">{val:,}</div><div class="kpi-label">{label}</div>')
        if sub:
            h.append(f'<div class="kpi-sub">{sub}</div>')
        h.append('</div>')
    h.append('</div>')

    # Distribution by nivel
    h.append('<div class="section-card"><h3>Distribución por nivel educativo</h3><div class="nivel-bars">')
    for nivel in NIVEL_ORDER:
        cnt = niveles.get(nivel, 0)
        pct = round(cnt / total * 100) if total else 0
        color = NIVEL_COLORS.get(nivel, "#999")
        h.append(f'''<div class="nivel-bar-row">
            <span class="nivel-bar-label">{nivel}</span>
            <div class="nivel-bar-track"><div class="nivel-bar-fill" style="width:{pct}%;background:{color}"></div></div>
            <span class="nivel-bar-count">{cnt}</span>
        </div>''')
    h.append('</div></div>')

    # Insights
    h.append('<div class="section-card"><h3>Diagnóstico automático</h3><div class="insights-list">')
    icons = {"ok": "✅", "warn": "⚠️", "alert": "🔴", "info": "💡"}
    for kind, title, detail in insights:
        h.append(f'''<div class="insight-row {kind}">
            <span class="insight-icon">{icons.get(kind, "")}</span>
            <div class="insight-body"><div class="insight-title">{_esc(title)}</div>''')
        if detail:
            h.append(f'<div class="insight-detail">{_esc(detail)}</div>')
        h.append('</div></div>')
    h.append('</div></div>')

    # Coverage overview
    h.append('<div class="section-card"><h3>Cobertura de piezas por escuela</h3>')
    h.append('<div class="coverage-grid">')
    for c in sorted(coverage_data, key=lambda x: x["pct"]):
        bar_color = "#c62828" if c["pct"] < 40 else "#e65100" if c["pct"] < 70 else "#2e7d32"
        nivel_color = NIVEL_COLORS.get(c["nivel"], "#999")
        h.append(f'''<div class="coverage-item" data-eid="{c['eid']}" data-nivel="{_esc(c['nivel'])}">
            <div class="coverage-header">
                <span class="coverage-name">{_esc(c["name"])}</span>
                <span class="coverage-pct" style="color:{bar_color}">{c["pct"]}%</span>
            </div>
            <div class="coverage-bar-track">
                <div class="coverage-bar-fill" style="width:{c["pct"]}%;background:{bar_color}"></div>
            </div>
            <div class="coverage-detail">{c["has"]} de {c["total"]} piezas · <span style="color:{nivel_color}">{c["nivel"]}</span></div>
        </div>''')
    h.append('</div></div>')

    return "\n".join(h)


def build_pieces(school_levels, pieces_raw, multi_level_ids, default_na=None):
    pieces_map = {}
    for eid, nivel, tipo, cnt in pieces_raw:
        pieces_map[(eid, nivel, tipo)] = cnt

    all_tipos = list(PIEZA_ORDER)

    niveles = OrderedDict()
    for sl in school_levels:
        n = sl["nivel_nombre"]
        if n not in niveles:
            niveles[n] = []
        niveles[n].append(sl)

    h = []

    # Config toolbar
    h.append('''<div class="filter-bar" style="justify-content:space-between">
        <div style="display:flex;align-items:center;gap:8px">
            <span style="font-size:12px;color:var(--text-muted)">Leyenda:</span>
            <span class="legend-chip has-1">✓ Tiene</span>
            <span class="legend-chip miss">— Falta</span>
            <span class="legend-chip na">✕ No aplica</span>
        </div>
        <button class="btn btn-outline" id="piezasConfigBtn" onclick="togglePiezasConfig()">
            <span id="piezasConfigIcon">⚙️</span> <span id="piezasConfigText">Configurar</span>
        </button>
    </div>''')
    h.append('<div id="piezasConfigBanner" class="config-banner" style="display:none">'
             'Modo configuración activo — haz clic en las celdas <b>—</b> para marcar como <b>✕ No aplica</b>, '
             'o clic en <b>✕</b> para revertir a <b>— Falta</b>.</div>')

    for nivel in NIVEL_ORDER:
        if nivel not in niveles:
            continue
        schools = niveles[nivel]
        nivel_color = NIVEL_COLORS.get(nivel, "#999")
        h.append(f'<div class="section-card"><h3><span class="nivel-dot" style="background:{nivel_color}"></span>{_esc(nivel)} <span class="count-label">{len(schools)} escuelas</span></h3>')
        h.append('<div class="table-scroll"><table class="pieces-table">')
        h.append('<thead><tr><th class="col-idx">#</th><th class="col-school">Escuela</th>')
        for t in all_tipos:
            short = t.replace("Pants ", "P·").replace("Suelto", "S")
            h.append(f'<th class="col-piece" title="{_esc(t)}">{_esc(short)}</th>')
        h.append('<th class="col-bar">Cobertura</th></tr></thead><tbody>')

        for i, sl in enumerate(schools, 1):
            eid = sl["escuela_id"]
            h.append(f'<tr data-school="{_esc(sl["display_name"])}" data-eid="{eid}" data-nivel="{_esc(nivel)}">')
            h.append(f'<td class="col-idx">{i}</td><td class="school-name">{_esc(sl["display_name"])}</td>')
            for t in all_tipos:
                cnt = pieces_map.get((eid, nivel, t))
                if cnt:
                    intensity = "has-1" if cnt == 1 else "has-2" if cnt == 2 else "has-3"
                    label = str(cnt) if cnt > 1 else "✓"
                    h.append(f'<td class="piece-cell {intensity}" title="{_esc(t)}: {cnt}" data-tipo="{_esc(t)}">{label}</td>')
                else:
                    h.append(f'<td class="piece-cell miss" title="{_esc(t)}: falta" data-tipo="{_esc(t)}" onclick="toggleNA(this)">—</td>')
            h.append(f'''<td class="col-bar-cell">
                <div class="inline-bar-track"><div class="inline-bar-fill"></div></div>
                <span class="inline-bar-pct"></span>
            </td>''')
            h.append('</tr>')

        h.append('</tbody></table></div></div>')

    # Embed tipos count for JS coverage calculation + default NA marks
    h.append(f'<script>window.__allTipos = {json.dumps(all_tipos)};')
    h.append(f'window.__defaultNA = {json.dumps(default_na or {})};</script>')

    return "\n".join(h)


def build_tariffs(catalog_rows, catalog_cols, multi_level_ids):
    col_idx = {c: i for i, c in enumerate(catalog_cols)}
    schools = OrderedDict()

    for row in catalog_rows:
        eid = row[col_idx["escuela_id"]]
        ename = row[col_idx["escuela"]]
        nivel = row[col_idx["nivel"]]
        pid = row[col_idx["producto_id"]]
        pname = row[col_idx["nombre_base"]]
        tipo = row[col_idx["tipo_pieza"]]
        display = f"{ename} {nivel}" if eid in multi_level_ids else ename

        if display not in schools:
            schools[display] = {"nivel": nivel, "products": OrderedDict()}
        if pid not in schools[display]["products"]:
            schools[display]["products"][pid] = {"nombre": pname, "tipo": tipo, "variants": []}

        vid = row[col_idx["variante_id"]]
        if vid is None:
            continue
        schools[display]["products"][pid]["variants"].append({
            "sku": row[col_idx["sku"]] or "",
            "talla": row[col_idx["talla"]] or "-",
            "color": row[col_idx["color"]] or "Sin color",
            "precio": float(row[col_idx["precio_venta"]]) if row[col_idx["precio_venta"]] else 0,
            "stock": row[col_idx["stock_actual"]] or 0,
            "activo": bool(row[col_idx["v_activo"]]),
        })

    # Build JSON blob for JS comparison engine
    tariff_json = {}
    for school_name, sdata in schools.items():
        tariff_json[school_name] = {"nivel": sdata["nivel"], "products": []}
        prods_sorted = sorted(
            sdata["products"].items(),
            key=lambda x: (PIEZA_ORDER.index(x[1]["tipo"]) if x[1]["tipo"] in PIEZA_ORDER else 99, x[1]["nombre"]),
        )
        for pid, pdata in prods_sorted:
            active = [v for v in pdata["variants"] if v["activo"]]
            if not active:
                continue
            tariff_json[school_name]["products"].append({
                "nombre": pdata["nombre"], "tipo": pdata["tipo"],
                "variants": [
                    {"s": v["sku"], "t": v["talla"], "c": v["color"], "p": v["precio"], "k": v["stock"]}
                    for v in sorted(active, key=lambda v: talla_sort_key(v["talla"]))
                ],
            })

    h = []

    # Comparison panel (hidden by default)
    h.append('''<div id="tariffComparePanel" class="compare-panel" style="display:none">
        <div class="compare-header">
            <h3>Comparar escuelas</h3>
            <div class="compare-slots">
                <span id="compareSlot1" class="compare-slot empty" onclick="clearCompareSlot(1)">Selecciona escuela...</span>
                <span class="compare-vs">vs</span>
                <span id="compareSlot2" class="compare-slot empty" onclick="clearCompareSlot(2)">Selecciona escuela...</span>
            </div>
            <button class="btn btn-sm" onclick="runComparison()">Comparar</button>
            <button class="btn btn-sm btn-ghost" onclick="clearComparison()">Limpiar</button>
        </div>
        <div id="compareResult" class="compare-result"></div>
    </div>''')

    # Filter bar
    h.append('''<div class="filter-bar">
        <input type="text" id="tariffSearch" placeholder="Buscar escuela..." class="search-box" oninput="filterTariffs()">
        <button class="btn btn-outline" onclick="toggleCompareMode()"><span id="compareBtnText">Comparar escuelas</span></button>
    </div>''')

    schools_sorted = sorted(
        schools.items(),
        key=lambda x: (NIVEL_ORDER.index(x[1]["nivel"]) if x[1]["nivel"] in NIVEL_ORDER else 99, x[0]),
    )
    current_nivel = None

    for school_name, sdata in schools_sorted:
        # Section header per nivel (collapsible)
        if sdata["nivel"] != current_nivel:
            if current_nivel is not None:
                h.append('</div></div>')  # close previous nivel-section-body + nivel-section
            current_nivel = sdata["nivel"]
            n_color = NIVEL_COLORS.get(current_nivel, "#999")
            n_count = sum(1 for _, sd in schools_sorted if sd["nivel"] == current_nivel)
            h.append(f'<div class="nivel-section" data-nivel="{_esc(current_nivel)}">')
            h.append(f'<div class="nivel-section-header" onclick="this.parentElement.classList.toggle(\'nivel-collapsed\')" style="border-left:4px solid {n_color};padding:8px 14px;margin:18px 0 0;background:var(--card-bg);border-radius:var(--radius-sm);font-weight:700;font-size:14px;color:var(--text);display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none">')
            h.append(f'<span class="nivel-dot" style="background:{n_color}"></span>{_esc(current_nivel)}<span style="font-weight:400;font-size:12px;color:var(--text-muted)">({n_count} escuelas)</span><span class="nivel-arrow">▾</span></div>')
            h.append('<div class="nivel-section-body">')

        prods = sdata["products"]
        nivel_color = NIVEL_COLORS.get(sdata["nivel"], "#999")
        active_prods = {pid: p for pid, p in prods.items() if any(v["activo"] for v in p["variants"])}
        prod_count = len(active_prods)
        total_variants = sum(sum(1 for v in p["variants"] if v["activo"]) for p in active_prods.values())

        # Price range for school
        all_school_prices = []
        for p in active_prods.values():
            for v in p["variants"]:
                if v["activo"] and v["precio"]:
                    all_school_prices.append(v["precio"])
        price_range = ""
        if all_school_prices:
            lo, hi = min(all_school_prices), max(all_school_prices)
            price_range = f"${lo:,.0f}–${hi:,.0f}" if lo != hi else f"${lo:,.0f}"

        esc_name_js = _esc(school_name).replace("'", "\\'")

        h.append(f'<div class="school-card tariff-card" data-school="{_esc(school_name)}">')
        h.append(f'<div class="card-header">')
        h.append(f'<div class="card-title-row" onclick="this.closest(\'.tariff-card\').classList.toggle(\'collapsed\')" style="cursor:pointer;flex:1;display:flex;align-items:center;gap:10px">')
        h.append(f'<span class="nivel-dot" style="background:{nivel_color}"></span><span class="card-title">{_esc(school_name)}</span></div>')
        h.append(f'<div class="card-actions">')
        h.append(f'<span class="meta-chip">{prod_count} prod.</span>')
        h.append(f'<span class="meta-chip">{total_variants} var.</span>')
        if price_range:
            h.append(f'<span class="meta-chip price-range">{price_range}</span>')
        h.append(f'<button class="btn-icon" title="Copiar tarifario" onclick="event.stopPropagation();copyTariff(\'{esc_name_js}\')">📋</button>')
        h.append(f'<button class="btn-icon" title="Imprimir tarifario" onclick="event.stopPropagation();printTariff(\'{esc_name_js}\')">🖨️</button>')
        h.append(f'<button class="btn-icon compare-btn" title="Agregar a comparación" onclick="event.stopPropagation();addToCompare(\'{esc_name_js}\')" style="display:none">⚖️</button>')
        h.append(f'<span class="toggle-arrow" onclick="this.closest(\'.tariff-card\').classList.toggle(\'collapsed\')" style="cursor:pointer">▾</span>')
        h.append('</div></div>')

        h.append('<div class="card-body">')

        # Group by tipo, sorted by PIEZA_ORDER
        by_tipo = OrderedDict()
        for pid, pdata in active_prods.items():
            t = pdata["tipo"]
            if t not in by_tipo:
                by_tipo[t] = []
            by_tipo[t].append((pid, pdata))
        by_tipo = OrderedDict(
            sorted(by_tipo.items(), key=lambda x: PIEZA_ORDER.index(x[0]) if x[0] in PIEZA_ORDER else 99)
        )

        for tipo, products in by_tipo.items():
            h.append(f'<div class="tariff-tipo-group"><div class="tipo-header">{_esc(tipo)}</div>')
            for pid, pdata in products:
                active = [v for v in pdata["variants"] if v["activo"]]
                if not active:
                    continue
                sorted_active = sorted(active, key=lambda v: talla_sort_key(v["talla"]))
                unique_colors = set(v["color"] for v in sorted_active)
                single_color = len(unique_colors) <= 1
                total_stock = sum(v["stock"] for v in sorted_active)
                stock_cls = "stock-zero" if total_stock == 0 else "stock-low" if total_stock < 10 else "stock-ok"

                # Build variant detail JSON for drill-down
                vdata = json.dumps([{"s": v["sku"], "t": v["talla"], "c": v["color"], "p": v["precio"], "k": v["stock"]} for v in sorted_active], ensure_ascii=False)

                h.append(f'<div class="tariff-product-row" data-variants=\'{_esc(vdata)}\'>')
                h.append(f'<div class="tariff-top" onclick="toggleDrilldown(this.parentElement)">')
                h.append(f'<span class="tariff-name">{_esc(pdata["nombre"])}</span>')
                h.append(f'<span class="tariff-stock {stock_cls}" title="Stock total">{total_stock}</span>')
                h.append(f'<span class="drill-arrow">›</span></div>')
                h.append('<div class="tariff-chips">')

                if single_color:
                    prices = {}
                    for v in sorted_active:
                        prices[v["talla"]] = v["precio"]
                    all_tallas = sorted(prices.keys(), key=talla_sort_key)
                    price_groups = OrderedDict()
                    for t in all_tallas:
                        p = prices[t]
                        if p not in price_groups:
                            price_groups[p] = []
                        price_groups[p].append(t)
                    all_prices = list(price_groups.keys())
                    min_p, max_p = min(all_prices), max(all_prices)
                    for price, tallas in price_groups.items():
                        trange = f"{tallas[0]}–{tallas[-1]}" if len(tallas) > 2 else ", ".join(tallas)
                        chip_cls = "price-chip"
                        if len(all_prices) > 1:
                            chip_cls += " price-low" if price == min_p else " price-high" if price == max_p else ""
                        h.append(f'<span class="{chip_cls}"><span class="chip-talla">{_esc(trange)}</span><span class="chip-price">${price:,.0f}</span></span>')
                else:
                    for color in sorted(unique_colors):
                        cvars = [v for v in sorted_active if v["color"] == color]
                        price_groups = OrderedDict()
                        for v in cvars:
                            p = v["precio"]
                            if p not in price_groups:
                                price_groups[p] = []
                            price_groups[p].append(v["talla"])
                        h.append(f'<div class="color-row"><span class="color-label">{_esc(color)}</span>')
                        for price, tallas in price_groups.items():
                            trange = f"{tallas[0]}–{tallas[-1]}" if len(tallas) > 2 else ", ".join(tallas)
                            h.append(f'<span class="price-chip"><span class="chip-talla">{_esc(trange)}</span><span class="chip-price">${price:,.0f}</span></span>')
                        h.append('</div>')

                h.append('</div>')

                # Drill-down detail (hidden by default)
                h.append('<div class="drilldown" style="display:none"><table class="drill-table">')
                h.append('<thead><tr><th>SKU</th><th>Talla</th><th>Color</th><th>Precio</th><th>Stock</th></tr></thead><tbody>')
                for v in sorted_active:
                    sk_cls = "val-zero" if v["stock"] == 0 else ""
                    h.append(f'<tr><td class="sku-cell">{_esc(v["sku"])}</td><td>{_esc(v["talla"])}</td><td>{_esc(v["color"])}</td>')
                    h.append(f'<td class="num-cell">${v["precio"]:,.0f}</td><td class="num-cell {sk_cls}">{v["stock"]}</td></tr>')
                h.append('</tbody></table>')
                h.append(f'<button class="btn btn-sm btn-ghost" onclick="copySkus(this)">Copiar SKUs</button>')
                h.append('</div></div>')

            h.append('</div>')

        h.append('</div></div>')

    if current_nivel is not None:
        h.append('</div></div>')  # close last nivel-section-body + nivel-section

    # Embed tariff data for comparison
    h.append(f'<script>window.__tariffData = {json.dumps(tariff_json, ensure_ascii=False)};</script>')

    return "\n".join(h)


def build_catalog(catalog_rows, catalog_cols, multi_level_ids, pieces_raw):
    col_idx = {c: i for i, c in enumerate(catalog_cols)}
    all_tipos = [t for t in PIEZA_ORDER if any(r[2] == t for r in pieces_raw)]

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
            schools[display] = {"nivel": nivel, "eid": eid, "products": OrderedDict()}
        if pid not in schools[display]["products"]:
            schools[display]["products"][pid] = {"nombre": pname, "tipo": tipo, "variants": []}

        vid = row[col_idx["variante_id"]]
        if vid is not None:
            schools[display]["products"][pid]["variants"].append({
                "sku": row[col_idx["sku"]], "talla": row[col_idx["talla"]] or "-",
                "color": row[col_idx["color"]] or "-", "precio": row[col_idx["precio_venta"]],
                "stock": row[col_idx["stock_actual"]], "activo": row[col_idx["v_activo"]],
            })

    # Pieces per school for coverage
    pieces_map = defaultdict(set)
    for eid, nivel, tipo, cnt in pieces_raw:
        pieces_map[(eid, nivel)].add(tipo)

    h = []
    h.append('''<div class="filter-bar">
        <input type="text" id="catalogSearch" placeholder="Buscar escuela, producto, SKU..." class="search-box" oninput="filterCatalog()">
        <select id="catalogNivel" class="filter-select" onchange="filterCatalog()"><option value="">Todos los niveles</option>''')
    for n in NIVEL_ORDER:
        h.append(f'<option value="{n}">{n}</option>')
    h.append('</select></div>')

    schools_sorted_cat = sorted(
        schools.items(),
        key=lambda x: (NIVEL_ORDER.index(x[1]["nivel"]) if x[1]["nivel"] in NIVEL_ORDER else 99, x[0]),
    )
    current_nivel_cat = None

    for school_name, sdata in schools_sorted_cat:
        # Section header per nivel (collapsible)
        if sdata["nivel"] != current_nivel_cat:
            if current_nivel_cat is not None:
                h.append('</div></div>')  # close previous nivel-section-body + nivel-section
            current_nivel_cat = sdata["nivel"]
            n_color = NIVEL_COLORS.get(current_nivel_cat, "#999")
            n_count = sum(1 for _, sd in schools_sorted_cat if sd["nivel"] == current_nivel_cat)
            h.append(f'<div class="nivel-section" data-nivel="{_esc(current_nivel_cat)}">')
            h.append(f'<div class="nivel-section-header" onclick="this.parentElement.classList.toggle(\'nivel-collapsed\')" style="border-left:4px solid {n_color};padding:8px 14px;margin:18px 0 0;background:var(--card-bg);border-radius:var(--radius-sm);font-weight:700;font-size:14px;color:var(--text);display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none">')
            h.append(f'<span class="nivel-dot" style="background:{n_color}"></span>{_esc(current_nivel_cat)}<span style="font-weight:400;font-size:12px;color:var(--text-muted)">({n_count} escuelas)</span><span class="nivel-arrow">▾</span></div>')
            h.append('<div class="nivel-section-body">')

        prods = sdata["products"]
        nivel_color = NIVEL_COLORS.get(sdata["nivel"], "#999")
        total_active = sum(sum(1 for v in p["variants"] if v["activo"]) for p in prods.values())
        total_inactive = sum(sum(1 for v in p["variants"] if not v["activo"]) for p in prods.values())
        total_stock = sum(sum(v["stock"] or 0 for v in p["variants"] if v["activo"]) for p in prods.values())
        tipos_in = pieces_map.get((sdata["eid"], sdata["nivel"]), set())
        cov = len(tipos_in)
        cov_pct = round(cov / len(all_tipos) * 100) if all_tipos else 0
        cov_color = "#c62828" if cov_pct < 40 else "#e65100" if cov_pct < 70 else "#2e7d32"

        h.append(f'<div class="school-card" data-school="{_esc(school_name)}" data-nivel="{_esc(sdata["nivel"])}">')
        h.append(f'<div class="card-header" onclick="this.parentElement.classList.toggle(\'collapsed\')">')
        h.append(f'<div class="card-title-row"><span class="nivel-dot" style="background:{nivel_color}"></span><span class="card-title">{_esc(school_name)}</span></div>')
        h.append(f'<div class="card-meta">')
        h.append(f'<span class="meta-chip">{len(prods)} prod.</span>')
        h.append(f'<span class="meta-chip">{total_active} var.</span>')
        h.append(f'<span class="meta-chip stock-chip-{("zero" if total_stock == 0 else "ok")}">Stock: {total_stock}</span>')
        h.append(f'<span class="meta-chip" style="color:{cov_color}">{cov}/{len(all_tipos)} piezas</span>')
        if total_inactive > 0:
            h.append(f'<span class="meta-chip warn">{total_inactive} inact.</span>')
        h.append('<span class="toggle-arrow">▾</span></div></div>')
        h.append('<div class="card-body">')

        prods_sorted = sorted(
            prods.items(),
            key=lambda x: (PIEZA_ORDER.index(x[1]["tipo"]) if x[1]["tipo"] in PIEZA_ORDER else 99, x[1]["nombre"]),
        )
        for pid, pdata in prods_sorted:
            if not pdata["variants"]:
                continue
            active_v = [v for v in pdata["variants"] if v["activo"]]
            prices = sorted(set(float(v["precio"]) for v in active_v if v["precio"]))
            tallas = sorted(set(v["talla"] for v in active_v), key=talla_sort_key)
            colors = sorted(set(v["color"] for v in active_v if v["color"] not in ("-", "Sin color")))
            prod_stock = sum(v["stock"] or 0 for v in active_v)
            price_str = f"${prices[0]:,.0f}" if len(prices) == 1 else f"${prices[0]:,.0f}–${prices[-1]:,.0f}" if prices else "—"

            stock_cls = "stock-zero" if prod_stock == 0 else "stock-low" if prod_stock < 10 else "stock-ok"

            h.append(f'<div class="product-card" data-name="{_esc(pdata["nombre"])}">')
            h.append(f'<div class="prod-top"><span class="tipo-tag">{_esc(pdata["tipo"])}</span><span class="prod-name">{_esc(pdata["nombre"])}</span><span class="prod-price">{price_str}</span></div>')
            h.append('<div class="prod-details">')

            # Tallas as chips
            h.append('<div class="chip-group"><span class="chip-label">Tallas</span>')
            for t in tallas:
                h.append(f'<span class="talla-chip">{_esc(t)}</span>')
            h.append('</div>')

            # Colors as chips
            if colors:
                h.append('<div class="chip-group"><span class="chip-label">Colores</span>')
                for c in colors:
                    h.append(f'<span class="color-chip">{_esc(c)}</span>')
                h.append('</div>')

            # Stock bar
            max_stock = 200
            bar_w = min(prod_stock / max_stock * 100, 100)
            h.append(f'''<div class="stock-indicator {stock_cls}">
                <span class="chip-label">Stock</span>
                <div class="stock-bar-track"><div class="stock-bar-fill" style="width:{bar_w}%"></div></div>
                <span class="stock-num">{prod_stock}</span>
            </div>''')

            h.append(f'<span class="var-count">{len(active_v)} variantes</span>')
            h.append('</div></div>')

        h.append('</div></div>')

    if current_nivel_cat is not None:
        h.append('</div></div>')  # close last nivel-section-body + nivel-section

    return "\n".join(h)


def build_missing(school_levels, pieces_raw, multi_level_ids):
    all_tipos = [t for t in PIEZA_ORDER if any(r[2] == t for r in pieces_raw)]

    pieces_by_nivel = defaultdict(lambda: defaultdict(int))
    for eid, nivel, tipo, cnt in pieces_raw:
        pieces_by_nivel[nivel][tipo] += 1

    nivel_school_counts = defaultdict(int)
    for sl in school_levels:
        nivel_school_counts[sl["nivel_nombre"]] += 1

    templates = {}
    for nivel, tipos in pieces_by_nivel.items():
        total = nivel_school_counts.get(nivel, 1)
        templates[nivel] = [t for t, c in tipos.items() if c >= total * 0.5]

    school_pieces = defaultdict(set)
    for eid, nivel, tipo, cnt in pieces_raw:
        school_pieces[(eid, nivel)].add(tipo)

    h = []
    # Template cards
    h.append('<div class="template-cards">')
    for nivel in NIVEL_ORDER:
        if nivel not in templates:
            continue
        tipos = sorted(templates[nivel], key=lambda t: PIEZA_ORDER.index(t) if t in PIEZA_ORDER else 99)
        nivel_color = NIVEL_COLORS.get(nivel, "#999")
        h.append(f'<div class="template-card"><div class="template-header" style="border-color:{nivel_color}"><span class="nivel-dot" style="background:{nivel_color}"></span>{nivel}</div>')
        h.append('<div class="template-pieces">')
        for t in tipos:
            h.append(f'<span class="template-piece">{_esc(t)}</span>')
        h.append('</div></div>')
    h.append('</div>')
    h.append('<p class="template-note">Piezas que &gt;50% de las escuelas del mismo nivel tienen. Las escuelas sin alguna aparecen abajo.</p>')

    sorted_niveles = OrderedDict()
    for sl in school_levels:
        n = sl["nivel_nombre"]
        if n not in sorted_niveles:
            sorted_niveles[n] = []
        sorted_niveles[n].append(sl)

    has_any = False
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
                missing_schools.append((sl, sorted(missing, key=lambda t: PIEZA_ORDER.index(t) if t in PIEZA_ORDER else 99), school_tipos))

        if not missing_schools:
            continue
        has_any = True
        nivel_color = NIVEL_COLORS.get(nivel, "#999")
        h.append(f'<div class="section-card"><h3><span class="nivel-dot" style="background:{nivel_color}"></span>{_esc(nivel)} <span class="count-label warn">{len(missing_schools)} con faltantes</span></h3>')

        for sl, missing, has_set in sorted(missing_schools, key=lambda x: -len(x[1])):
            severity = "severe" if len(missing) >= 4 else "moderate" if len(missing) >= 2 else "mild"
            has_list = sorted(has_set, key=lambda t: PIEZA_ORDER.index(t) if t in PIEZA_ORDER else 99)
            h.append(f'<div class="missing-row {severity}" data-eid="{sl["escuela_id"]}" data-nivel="{_esc(nivel)}">')
            h.append(f'<div class="missing-school">{_esc(sl["display_name"])}</div>')
            h.append(f'<div class="missing-pieces">')
            for m in missing:
                h.append(f'<span class="missing-tag" data-tipo="{_esc(m)}">{_esc(m)}</span>')
            h.append('</div>')
            h.append(f'<div class="has-pieces">Tiene: {_esc(", ".join(has_list))}</div>')
            h.append('</div>')

        h.append('</div>')

    if not has_any:
        h.append('<div class="all-good-card"><div class="all-good-icon">✅</div><div class="all-good-text">Todas las escuelas tienen las piezas base de su nivel.</div></div>')

    return "\n".join(h)


def build_variants(catalog_rows, catalog_cols, multi_level_ids):
    col_idx = {c: i for i, c in enumerate(catalog_cols)}
    products = OrderedDict()

    for row in catalog_rows:
        pid = row[col_idx["producto_id"]]
        if pid not in products:
            eid = row[col_idx["escuela_id"]]
            ename = row[col_idx["escuela"]]
            nivel = row[col_idx["nivel"]]
            display = f"{ename} {nivel}" if eid in multi_level_ids else ename
            products[pid] = {
                "nombre": row[col_idx["nombre_base"]], "escuela": display,
                "nivel": nivel, "tipo": row[col_idx["tipo_pieza"]],
                "activas": 0, "inactivas": 0,
                "tallas": set(), "colores": set(), "precios": set(), "stock": 0,
            }
        vid = row[col_idx["variante_id"]]
        if vid is None:
            continue
        p = products[pid]
        if row[col_idx["v_activo"]]:
            p["activas"] += 1
            t = row[col_idx["talla"]] or "-"
            c = row[col_idx["color"]] or "-"
            if t != "-":
                p["tallas"].add(t)
            if c not in ("-", "Sin color"):
                p["colores"].add(c)
            if row[col_idx["precio_venta"]]:
                p["precios"].add(float(row[col_idx["precio_venta"]]))
            p["stock"] += row[col_idx["stock_actual"]] or 0
        else:
            p["inactivas"] += 1

    h = []
    h.append('''<div class="filter-bar">
        <input type="text" id="variantSearch" placeholder="Buscar producto, escuela..." class="search-box" oninput="filterVariants()">
        <select id="variantFilter" class="filter-select" onchange="filterVariants()">
            <option value="">Todos</option>
            <option value="few">Pocas variantes (≤2)</option>
            <option value="inactive">Con inactivas</option>
            <option value="nostock">Sin stock</option>
            <option value="multicolor">Multi-color</option>
        </select>
    </div>''')

    h.append('<div class="table-scroll"><table class="variants-table" id="variantTable">')
    h.append('<thead><tr><th>Escuela</th><th>Producto</th><th>Tipo</th><th>Act.</th><th>Inact.</th><th>Tallas</th><th>Colores</th><th>Precio</th><th>Stock</th></tr></thead><tbody>')

    for pid, p in products.items():
        prices = sorted(p["precios"])
        tallas = sorted(p["tallas"], key=talla_sort_key)
        colores = sorted(p["colores"])
        price_str = f"${prices[0]:,.0f}" if len(prices) == 1 else f"${prices[0]:,.0f}–${prices[-1]:,.0f}" if prices else "—"

        classes = []
        if p["activas"] <= 2:
            classes.append("row-few")
        if p["inactivas"] > 0:
            classes.append("row-inactive")
        if p["stock"] == 0:
            classes.append("row-nostock")
        if len(colores) > 1:
            classes.append("row-multicolor")

        stock_cls = "val-zero" if p["stock"] == 0 else "val-low" if p["stock"] < 10 else ""
        inact_cls = "val-warn" if p["inactivas"] > 0 else ""

        h.append(f'<tr class="{" ".join(classes)}" data-school="{_esc(p["escuela"])}" data-name="{_esc(p["nombre"])}">')
        h.append(f'<td class="school-name">{_esc(p["escuela"])}</td>')
        h.append(f'<td>{_esc(p["nombre"])}</td>')
        h.append(f'<td><span class="tipo-tag sm">{_esc(p["tipo"])}</span></td>')
        h.append(f'<td class="num-cell">{p["activas"]}</td>')
        h.append(f'<td class="num-cell {inact_cls}">{p["inactivas"]}</td>')
        h.append(f'<td class="tallas-cell">{_esc(", ".join(tallas))}</td>')
        h.append(f'<td>{_esc(", ".join(colores)) if colores else "—"}</td>')
        h.append(f'<td class="num-cell">{price_str}</td>')
        # Stock with inline bar
        max_s = 200
        bar_w = min(p["stock"] / max_s * 100, 100) if p["stock"] > 0 else 0
        h.append(f'<td class="num-cell {stock_cls}"><div class="inline-stock"><div class="inline-stock-bar" style="width:{bar_w}%"></div><span>{p["stock"]}</span></div></td>')
        h.append('</tr>')

    h.append('</tbody></table></div>')
    return "\n".join(h)


# ---------------------------------------------------------------------------
# Full HTML
# ---------------------------------------------------------------------------

def generate_html(resumen, pieces, tariffs, catalog, missing, variants):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Panel de Uniformes — MAXIMODA</title>
<style>
/* ============ RESET & BASE ============ */
:root {{
    --brand: #87492c; --brand-light: #f5ebe0; --brand-dark: #5c3019;
    --bg: #f7f5f2; --card-bg: #ffffff; --text: #1a1a1a; --text-muted: #6b7280;
    --border: #e5e5e5; --border-light: #f0ede8;
    --green: #16a34a; --green-bg: #dcfce7; --red: #dc2626; --red-bg: #fef2f2;
    --orange: #ea580c; --orange-bg: #fff7ed; --blue: #2563eb; --blue-bg: #eff6ff;
    --purple: #7c3aed;
    --radius: 12px; --radius-sm: 8px; --radius-xs: 6px;
    --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.05), 0 2px 4px rgba(0,0,0,0.04);
    --shadow-lg: 0 10px 15px rgba(0,0,0,0.06), 0 4px 6px rgba(0,0,0,0.04);
    --transition: 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}}

[data-theme="dark"] {{
    --bg: #111111; --card-bg: #1c1c1e; --text: #f0f0f0; --text-muted: #9ca3af;
    --border: #2d2d2d; --border-light: #252525;
    --brand-light: #2a1a10; --green-bg: #0a2e14; --red-bg: #2a0a0a;
    --orange-bg: #2a1a0a; --blue-bg: #0a1a2e;
    --shadow: 0 1px 3px rgba(0,0,0,0.3); --shadow-md: 0 4px 6px rgba(0,0,0,0.3);
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', system-ui, sans-serif; font-size: 13px; color: var(--text); background: var(--bg); -webkit-font-smoothing: antialiased; }}

/* ============ LAYOUT ============ */
.topbar {{
    background: linear-gradient(135deg, var(--brand) 0%, var(--brand-dark) 100%);
    color: white; padding: 0 24px; height: 56px; display: flex; align-items: center;
    justify-content: space-between; position: sticky; top: 0; z-index: 100;
    box-shadow: 0 2px 12px rgba(135,73,44,0.3);
}}
.topbar h1 {{ font-size: 17px; font-weight: 700; letter-spacing: -0.3px; }}
.topbar .brand-accent {{ font-weight: 300; opacity: 0.8; }}
.topbar-right {{ display: flex; align-items: center; gap: 12px; }}
.topbar-date {{ font-size: 11px; opacity: 0.7; }}
.theme-toggle {{ background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.2);
    border-radius: 99px; width: 36px; height: 36px; cursor: pointer; display: flex;
    align-items: center; justify-content: center; font-size: 16px; transition: all var(--transition);
    color: white; backdrop-filter: blur(4px); }}
.theme-toggle:hover {{ background: rgba(255,255,255,0.25); transform: scale(1.08); }}

/* ---- Nivel collapsible sections ---- */
.nivel-section {{ margin-bottom: 4px; }}
.nivel-arrow {{ margin-left: auto; font-size: 14px; transition: transform var(--transition); color: var(--text-muted); }}
.nivel-collapsed .nivel-arrow {{ transform: rotate(-90deg); }}
.nivel-section-body {{ padding-top: 10px; transition: all var(--transition); }}
.nivel-collapsed .nivel-section-body {{ display: none; }}
.nivel-section-header:hover {{ background: var(--brand-light) !important; }}

.nav {{ display: flex; background: var(--card-bg); border-bottom: 1px solid var(--border);
    padding: 0 24px; position: sticky; top: 56px; z-index: 99; overflow-x: auto; }}
.nav-tab {{ padding: 12px 18px; cursor: pointer; font-weight: 600; font-size: 13px;
    color: var(--text-muted); border-bottom: 2px solid transparent;
    transition: all var(--transition); white-space: nowrap; user-select: none; }}
.nav-tab:hover {{ color: var(--brand); background: var(--brand-light); }}
.nav-tab.active {{ color: var(--brand); border-bottom-color: var(--brand); }}

.page {{ max-width: 1440px; margin: 0 auto; padding: 20px 24px; }}
.tab-panel {{ display: none; animation: fadeIn 0.3s ease; }}
.tab-panel.active {{ display: block; }}
@keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: translateY(0); }} }}

/* ============ KPI CARDS ============ */
.kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 20px; }}
.kpi-card {{ background: var(--card-bg); border-radius: var(--radius); padding: 20px;
    box-shadow: var(--shadow); border-left: 4px solid var(--brand); transition: transform var(--transition), box-shadow var(--transition); }}
.kpi-card:hover {{ transform: translateY(-2px); box-shadow: var(--shadow-md); }}
.kpi-card.school {{ border-left-color: var(--purple); }}
.kpi-card.product {{ border-left-color: var(--blue); }}
.kpi-card.variant {{ border-left-color: var(--green); }}
.kpi-card.inactive {{ border-left-color: var(--orange); }}
.kpi-value {{ font-size: 32px; font-weight: 800; letter-spacing: -1px; }}
.kpi-card.school .kpi-value {{ color: var(--purple); }}
.kpi-card.product .kpi-value {{ color: var(--blue); }}
.kpi-card.variant .kpi-value {{ color: var(--green); }}
.kpi-card.inactive .kpi-value {{ color: var(--orange); }}
.kpi-label {{ font-size: 13px; font-weight: 600; color: var(--text-muted); margin-top: 2px; }}
.kpi-sub {{ font-size: 11px; color: var(--text-muted); margin-top: 4px; }}

/* ============ SECTION CARDS ============ */
.section-card {{ background: var(--card-bg); border-radius: var(--radius); padding: 20px;
    box-shadow: var(--shadow); margin-bottom: 16px; }}
.section-card h3 {{ font-size: 15px; font-weight: 700; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }}
.count-label {{ font-size: 11px; font-weight: 600; color: var(--text-muted); background: var(--border-light); padding: 2px 10px; border-radius: 99px; }}
.count-label.warn {{ background: var(--orange-bg); color: var(--orange); }}

/* ============ NIVEL BARS ============ */
.nivel-bars {{ display: flex; flex-direction: column; gap: 10px; }}
.nivel-bar-row {{ display: flex; align-items: center; gap: 12px; }}
.nivel-bar-label {{ width: 100px; font-weight: 600; font-size: 13px; text-align: right; }}
.nivel-bar-track {{ flex: 1; height: 28px; background: var(--border-light); border-radius: 99px; overflow: hidden; }}
.nivel-bar-fill {{ height: 100%; border-radius: 99px; transition: width 0.6s ease; display: flex; align-items: center; justify-content: flex-end; padding-right: 10px;
    font-size: 11px; font-weight: 700; color: white; min-width: 30px; }}
.nivel-bar-count {{ width: 30px; font-weight: 700; font-size: 15px; }}
.nivel-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex-shrink: 0; }}

/* ============ INSIGHTS ============ */
.insights-list {{ display: flex; flex-direction: column; gap: 8px; }}
.insight-row {{ display: flex; align-items: flex-start; gap: 10px; padding: 10px 14px; border-radius: var(--radius-sm); }}
.insight-row.ok {{ background: var(--green-bg); }}
.insight-row.warn {{ background: var(--orange-bg); }}
.insight-row.alert {{ background: var(--red-bg); }}
.insight-row.info {{ background: var(--blue-bg); }}
.insight-icon {{ font-size: 16px; flex-shrink: 0; margin-top: 1px; }}
.insight-title {{ font-weight: 600; font-size: 13px; }}
.insight-detail {{ font-size: 12px; color: var(--text-muted); margin-top: 2px; }}

/* ============ COVERAGE ============ */
.coverage-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }}
.coverage-item {{ padding: 10px 12px; border-radius: var(--radius-sm); background: var(--bg); }}
.coverage-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }}
.coverage-name {{ font-weight: 600; font-size: 12px; }}
.coverage-pct {{ font-weight: 800; font-size: 14px; }}
.coverage-bar-track {{ height: 6px; background: var(--border-light); border-radius: 99px; overflow: hidden; }}
.coverage-bar-fill {{ height: 100%; border-radius: 99px; transition: width 0.6s ease; }}
.coverage-detail {{ font-size: 11px; color: var(--text-muted); margin-top: 4px; }}

/* ============ PIECES TABLE ============ */
.table-scroll {{ overflow-x: auto; }}
.pieces-table {{ border-collapse: separate; border-spacing: 0; width: 100%; font-size: 12px; }}
.pieces-table th {{ background: var(--brand); color: white; padding: 8px 6px; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }}
.pieces-table th:first-child {{ border-radius: var(--radius-xs) 0 0 0; }}
.pieces-table th:last-child {{ border-radius: 0 var(--radius-xs) 0 0; }}
.pieces-table td {{ padding: 6px 6px; border-bottom: 1px solid var(--border-light); text-align: center; }}
.pieces-table tbody tr {{ transition: background var(--transition); }}
.pieces-table tbody tr:hover {{ background: var(--brand-light); }}
.col-idx {{ width: 30px; color: var(--text-muted); font-size: 11px; }}
.col-school {{ text-align: left !important; min-width: 180px; }}
.school-name {{ text-align: left !important; font-weight: 600; white-space: nowrap; }}
.col-piece {{ width: 46px; }}
.piece-cell {{ font-size: 13px; font-weight: 700; }}
.piece-cell.has-1 {{ color: var(--green); background: color-mix(in srgb, var(--green) 8%, transparent); }}
.piece-cell.has-2 {{ color: #15803d; background: color-mix(in srgb, var(--green) 14%, transparent); }}
.piece-cell.has-3 {{ color: #166534; background: color-mix(in srgb, var(--green) 22%, transparent); }}
.piece-cell.miss {{ color: var(--red); font-weight: 400; cursor: default; }}
.piece-cell.na {{ color: var(--text-muted); font-weight: 400; opacity: 0.4; cursor: default; font-size: 11px; }}
.config-active .piece-cell.miss {{ cursor: pointer; }}
.config-active .piece-cell.miss:hover {{ background: color-mix(in srgb, var(--orange) 15%, transparent); }}
.config-active .piece-cell.na {{ cursor: pointer; }}
.config-active .piece-cell.na:hover {{ background: color-mix(in srgb, var(--blue) 15%, transparent); }}
.config-banner {{ background: var(--orange-bg); border: 1px solid var(--orange); border-radius: var(--radius-sm);
    padding: 10px 16px; font-size: 12px; color: var(--orange); margin-bottom: 12px; animation: fadeIn 0.3s ease; }}
.legend-chip {{ font-size: 11px; padding: 3px 10px; border-radius: 99px; font-weight: 600; }}
.legend-chip.has-1 {{ color: var(--green); background: var(--green-bg); }}
.legend-chip.miss {{ color: var(--red); background: var(--red-bg); }}
.legend-chip.na {{ color: var(--text-muted); background: var(--border-light); }}
.col-bar {{ width: 130px; }}
.col-bar-cell {{ white-space: nowrap; }}
.inline-bar-track {{ display: inline-block; width: 70px; height: 8px; background: var(--border-light); border-radius: 99px; overflow: hidden; vertical-align: middle; margin-right: 6px; }}
.inline-bar-fill {{ height: 100%; border-radius: 99px; }}
.inline-bar-pct {{ font-size: 12px; font-weight: 700; }}

/* ============ SCHOOL CARDS (Catalog, Tariff) ============ */
.school-card {{ background: var(--card-bg); border-radius: var(--radius); margin-bottom: 10px;
    box-shadow: var(--shadow); overflow: hidden; transition: box-shadow var(--transition); }}
.school-card:hover {{ box-shadow: var(--shadow-md); }}
.card-header {{ display: flex; align-items: center; justify-content: space-between;
    padding: 14px 18px; cursor: pointer; transition: background var(--transition); }}
.card-header:hover {{ background: var(--brand-light); }}
.card-title-row {{ display: flex; align-items: center; gap: 10px; }}
.card-title {{ font-weight: 700; font-size: 14px; }}
.card-meta {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
.meta-chip {{ font-size: 11px; color: var(--text-muted); background: var(--border-light); padding: 2px 10px; border-radius: 99px; }}
.meta-chip.warn {{ color: var(--orange); background: var(--orange-bg); }}
.stock-chip-zero {{ color: var(--red) !important; background: var(--red-bg) !important; }}
.toggle-arrow {{ font-size: 14px; color: var(--text-muted); transition: transform var(--transition); }}
.collapsed .toggle-arrow {{ transform: rotate(-90deg); }}
.collapsed .card-body {{ display: none; }}
.card-body {{ padding: 4px 18px 16px; }}

/* ============ PRODUCT CARDS (Catalog) ============ */
.product-card {{ padding: 10px 12px; border-radius: var(--radius-sm); margin-bottom: 4px;
    background: var(--bg); transition: all var(--transition); }}
.product-card:hover {{ background: var(--brand-light); transform: translateX(2px); }}
.prod-top {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
.prod-name {{ font-weight: 600; font-size: 13px; flex: 1; }}
.prod-price {{ font-weight: 700; font-size: 14px; color: var(--brand); }}
.prod-details {{ display: flex; align-items: center; gap: 12px; margin-top: 6px; flex-wrap: wrap; }}
.tipo-tag {{ background: var(--brand-light); color: var(--brand); padding: 3px 10px; border-radius: 99px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px; }}
.tipo-tag.sm {{ padding: 2px 8px; font-size: 9px; }}
.chip-group {{ display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }}
.chip-label {{ font-size: 10px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.3px; margin-right: 2px; }}
.talla-chip {{ background: var(--green-bg); color: var(--green); padding: 1px 7px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
.color-chip {{ background: var(--blue-bg); color: var(--blue); padding: 1px 7px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
.var-count {{ font-size: 11px; font-weight: 700; color: var(--brand); }}

/* Stock indicators */
.stock-indicator {{ display: flex; align-items: center; gap: 6px; }}
.stock-bar-track {{ width: 50px; height: 6px; background: var(--border-light); border-radius: 99px; overflow: hidden; }}
.stock-bar-fill {{ height: 100%; border-radius: 99px; }}
.stock-ok .stock-bar-fill {{ background: var(--green); }}
.stock-low .stock-bar-fill {{ background: var(--orange); }}
.stock-zero .stock-bar-fill {{ background: var(--red); width: 0 !important; }}
.stock-num {{ font-size: 12px; font-weight: 700; }}
.stock-ok .stock-num {{ color: var(--green); }}
.stock-low .stock-num {{ color: var(--orange); }}
.stock-zero .stock-num {{ color: var(--red); }}

/* ============ TARIFF ============ */
.tariff-tipo-group {{ margin-bottom: 14px; }}
.tipo-header {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted);
    padding: 6px 0; border-bottom: 1px solid var(--border-light); margin-bottom: 4px; }}
.tariff-product-row {{ border-radius: var(--radius-sm); margin-bottom: 2px; transition: background var(--transition); }}
.tariff-product-row:hover {{ background: var(--bg); }}
.tariff-product-row.expanded {{ background: var(--brand-light); border-radius: var(--radius-sm); }}
.tariff-top {{ display: flex; align-items: center; gap: 8px; padding: 6px 8px; cursor: pointer; }}
.tariff-name {{ font-weight: 600; font-size: 12px; flex: 1; }}
.tariff-stock {{ font-size: 11px; font-weight: 700; padding: 1px 8px; border-radius: 99px; }}
.tariff-stock.stock-ok {{ color: var(--green); background: var(--green-bg); }}
.tariff-stock.stock-low {{ color: var(--orange); background: var(--orange-bg); }}
.tariff-stock.stock-zero {{ color: var(--red); background: var(--red-bg); }}
.drill-arrow {{ color: var(--text-muted); font-size: 16px; transition: transform var(--transition); font-weight: 300; }}
.tariff-product-row.expanded .drill-arrow {{ transform: rotate(90deg); color: var(--brand); }}
.tariff-chips {{ display: flex; gap: 6px; flex-wrap: wrap; padding: 0 8px 6px; }}
.price-chip {{ display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px;
    border-radius: var(--radius-xs); background: var(--bg); font-size: 12px;
    border: 1px solid var(--border-light); transition: all var(--transition); }}
.price-chip:hover {{ box-shadow: var(--shadow); transform: translateY(-1px); }}
.chip-talla {{ color: var(--text-muted); font-size: 11px; }}
.chip-price {{ font-weight: 700; color: var(--text); }}
.price-low {{ border-color: var(--green); background: var(--green-bg); }}
.price-low .chip-price {{ color: var(--green); }}
.price-high {{ border-color: var(--orange); background: var(--orange-bg); }}
.price-high .chip-price {{ color: var(--orange); }}
.color-row {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin: 2px 0; padding-left: 8px; }}
.color-label {{ font-weight: 600; font-size: 11px; color: var(--brand); min-width: 80px; }}

/* Drill-down detail table */
.drilldown {{ padding: 6px 8px 10px; animation: fadeIn 0.2s ease; }}
.drill-table {{ border-collapse: separate; border-spacing: 0; width: 100%; font-size: 11px; background: var(--card-bg); border-radius: var(--radius-xs); overflow: hidden; }}
.drill-table th {{ background: var(--brand-dark); color: white; padding: 6px 8px; font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px; text-align: left; }}
.drill-table td {{ padding: 5px 8px; border-bottom: 1px solid var(--border-light); }}
.drill-table tbody tr:hover {{ background: var(--brand-light); }}
.sku-cell {{ font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace; font-size: 10px; color: var(--text-muted); cursor: pointer; }}
.sku-cell:hover {{ color: var(--brand); text-decoration: underline; }}

/* Card actions */
.card-actions {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
.btn-icon {{ background: none; border: none; cursor: pointer; font-size: 14px; padding: 4px 6px;
    border-radius: var(--radius-xs); transition: all var(--transition); opacity: 0.6; }}
.btn-icon:hover {{ opacity: 1; background: var(--brand-light); }}
.price-range {{ color: var(--brand) !important; font-weight: 700 !important; }}

/* Buttons */
.btn {{ padding: 8px 16px; border: none; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600;
    cursor: pointer; transition: all var(--transition); background: var(--brand); color: white; }}
.btn:hover {{ filter: brightness(1.1); transform: translateY(-1px); }}
.btn-sm {{ padding: 5px 12px; font-size: 11px; }}
.btn-outline {{ background: transparent; border: 2px solid var(--brand); color: var(--brand); }}
.btn-outline:hover {{ background: var(--brand); color: white; }}
.btn-outline.active {{ background: var(--brand); color: white; }}
.btn-ghost {{ background: transparent; color: var(--text-muted); }}
.btn-ghost:hover {{ background: var(--border-light); color: var(--text); }}

/* Comparison panel */
.compare-panel {{ background: var(--card-bg); border-radius: var(--radius); padding: 16px; margin-bottom: 14px;
    box-shadow: var(--shadow-md); border: 2px solid var(--brand); animation: fadeIn 0.3s ease; }}
.compare-header {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.compare-header h3 {{ font-size: 14px; margin: 0; }}
.compare-slots {{ display: flex; align-items: center; gap: 8px; flex: 1; }}
.compare-slot {{ padding: 6px 14px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600;
    background: var(--border-light); color: var(--text-muted); cursor: pointer; transition: all var(--transition); min-width: 150px; text-align: center; }}
.compare-slot.filled {{ background: var(--brand-light); color: var(--brand); }}
.compare-slot.filled:hover {{ background: var(--red-bg); color: var(--red); }}
.compare-vs {{ font-weight: 800; color: var(--text-muted); font-size: 13px; }}
.compare-result {{ margin-top: 14px; }}
.compare-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.compare-col {{ background: var(--bg); border-radius: var(--radius-sm); padding: 12px; }}
.compare-col h4 {{ font-size: 13px; margin-bottom: 10px; border-bottom: 2px solid var(--brand); padding-bottom: 6px; }}
.compare-prod {{ padding: 4px 0; font-size: 12px; display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-light); }}
.compare-prod-name {{ font-weight: 600; }}
.compare-prod-price {{ font-weight: 700; color: var(--brand); }}
.compare-diff {{ background: var(--orange-bg); padding: 2px 6px; border-radius: 4px; font-size: 10px; color: var(--orange); font-weight: 700; margin-left: 4px; }}
.compare-only {{ opacity: 0.5; font-style: italic; }}

/* ============ FILTER BAR ============ */
.filter-bar {{ display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }}
.search-box {{ flex: 1; min-width: 200px; padding: 10px 16px; border: 2px solid var(--border);
    border-radius: var(--radius-sm); font-size: 13px; background: var(--card-bg); color: var(--text);
    outline: none; transition: border-color var(--transition), box-shadow var(--transition); }}
.search-box:focus {{ border-color: var(--brand); box-shadow: 0 0 0 3px rgba(135,73,44,0.15); }}
.filter-select {{ padding: 10px 16px; border: 2px solid var(--border); border-radius: var(--radius-sm);
    font-size: 13px; background: var(--card-bg); color: var(--text); cursor: pointer; }}

/* ============ MISSING ============ */
.template-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 12px; }}
.template-card {{ background: var(--card-bg); border-radius: var(--radius); padding: 14px; box-shadow: var(--shadow); }}
.template-header {{ font-weight: 700; font-size: 14px; padding-bottom: 8px; margin-bottom: 8px;
    border-bottom: 3px solid var(--border); display: flex; align-items: center; gap: 8px; }}
.template-pieces {{ display: flex; flex-wrap: wrap; gap: 4px; }}
.template-piece {{ background: var(--green-bg); color: var(--green); padding: 3px 10px; border-radius: 99px; font-size: 11px; font-weight: 600; }}
.template-note {{ font-size: 12px; color: var(--text-muted); margin-bottom: 16px; }}
.missing-row {{ display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: var(--radius-sm); margin-bottom: 4px; flex-wrap: wrap; }}
.missing-row.severe {{ background: var(--red-bg); }}
.missing-row.moderate {{ background: var(--orange-bg); }}
.missing-row.mild {{ background: var(--blue-bg); }}
.missing-school {{ font-weight: 700; min-width: 200px; }}
.missing-pieces {{ display: flex; gap: 4px; flex-wrap: wrap; }}
.missing-tag {{ background: var(--red); color: white; padding: 2px 10px; border-radius: 99px; font-size: 11px; font-weight: 600; }}
.missing-row.moderate .missing-tag {{ background: var(--orange); }}
.missing-row.mild .missing-tag {{ background: var(--blue); }}
.has-pieces {{ font-size: 11px; color: var(--text-muted); flex: 1; }}
.all-good-card {{ background: var(--green-bg); border-radius: var(--radius); padding: 40px; text-align: center; }}
.all-good-icon {{ font-size: 40px; margin-bottom: 8px; }}
.all-good-text {{ font-size: 16px; font-weight: 600; color: var(--green); }}

/* ============ VARIANTS TABLE ============ */
.variants-table {{ border-collapse: separate; border-spacing: 0; width: 100%; font-size: 12px; }}
.variants-table th {{ background: var(--brand); color: white; padding: 10px 8px; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; text-align: left; }}
.variants-table th:first-child {{ border-radius: var(--radius-xs) 0 0 0; }}
.variants-table th:last-child {{ border-radius: 0 var(--radius-xs) 0 0; }}
.variants-table td {{ padding: 8px; border-bottom: 1px solid var(--border-light); }}
.variants-table tbody tr {{ transition: background var(--transition); }}
.variants-table tbody tr:hover {{ background: var(--brand-light); }}
.num-cell {{ text-align: right; font-variant-numeric: tabular-nums; }}
.val-warn {{ color: var(--orange); font-weight: 700; }}
.val-zero {{ color: var(--red); font-weight: 700; }}
.val-low {{ color: var(--orange); }}
.tallas-cell {{ font-size: 11px; max-width: 220px; }}
.inline-stock {{ display: flex; align-items: center; gap: 6px; justify-content: flex-end; }}
.inline-stock-bar {{ height: 6px; background: var(--green); border-radius: 99px; min-width: 0; transition: width 0.4s ease; }}
.row-nostock .inline-stock-bar {{ background: var(--red); }}
.row-nostock td:last-child {{ background: var(--red-bg); }}

/* ============ PRINT ============ */
@media print {{
    .topbar, .nav {{ position: static; }}
    .nav {{ display: none; }}
    .tab-panel {{ display: block !important; page-break-before: always; }}
    .tab-panel:first-child {{ page-break-before: auto; }}
    .filter-bar {{ display: none; }}
    .school-card {{ break-inside: avoid; }}
    .collapsed .card-body {{ display: block !important; }}
    .kpi-card:hover, .product-card:hover, .school-card:hover {{ transform: none; box-shadow: var(--shadow); }}
}}
</style>
</head>
<body>

<div class="topbar">
    <h1>MAXIMODA <span class="brand-accent">— Panel de Uniformes</span></h1>
    <div class="topbar-right">
        <span class="topbar-date">{now}</span>
        <button class="theme-toggle" onclick="toggleTheme()" id="themeBtn" title="Cambiar tema">🌙</button>
    </div>
</div>

<div class="nav">
    <div class="nav-tab active" onclick="showTab('resumen')">Resumen</div>
    <div class="nav-tab" onclick="showTab('piezas')">Piezas</div>
    <div class="nav-tab" onclick="showTab('tarifarios')">Tarifarios</div>
    <div class="nav-tab" onclick="showTab('catalogo')">Catálogo</div>
    <div class="nav-tab" onclick="showTab('faltantes')">Faltantes</div>
    <div class="nav-tab" onclick="showTab('variantes')">Variantes</div>
</div>

<div class="page">
    <div id="resumen" class="tab-panel active">{resumen}</div>
    <div id="piezas" class="tab-panel">{pieces}</div>
    <div id="tarifarios" class="tab-panel">{tariffs}</div>
    <div id="catalogo" class="tab-panel">{catalog}</div>
    <div id="faltantes" class="tab-panel">{missing}</div>
    <div id="variantes" class="tab-panel">{variants}</div>
</div>

<script>
/* ---- Theme toggle ---- */
function toggleTheme() {{
    const html = document.documentElement;
    const isDark = html.getAttribute('data-theme') === 'dark';
    html.setAttribute('data-theme', isDark ? 'light' : 'dark');
    document.getElementById('themeBtn').textContent = isDark ? '🌙' : '☀️';
    localStorage.setItem('panel-theme', isDark ? 'light' : 'dark');
}}
(function() {{
    const saved = localStorage.getItem('panel-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? 'dark' : 'light');
    if (theme === 'dark') {{
        document.documentElement.setAttribute('data-theme', 'dark');
        document.addEventListener('DOMContentLoaded', () => {{
            const btn = document.getElementById('themeBtn');
            if (btn) btn.textContent = '☀️';
        }});
    }}
}})();

function showTab(id) {{
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    const names = ['resumen','piezas','tarifarios','catalogo','faltantes','variantes'];
    const idx = names.indexOf(id);
    if (idx >= 0) document.querySelectorAll('.nav-tab')[idx].classList.add('active');
}}

/* ---- Piezas: config mode & NA toggle ---- */
let piezasConfigMode = false;

function getPiezasNA() {{
    try {{ return JSON.parse(localStorage.getItem('piezas-na') || '{{}}'); }}
    catch {{ return {{}}; }}
}}
function savePiezasNA(na) {{ localStorage.setItem('piezas-na', JSON.stringify(na)); }}

function naKey(cell) {{
    const tr = cell.closest('tr');
    return tr.dataset.eid + '_' + tr.dataset.nivel + '_' + cell.dataset.tipo;
}}

function togglePiezasConfig() {{
    piezasConfigMode = !piezasConfigMode;
    const piezasTab = document.getElementById('piezas');
    piezasTab.classList.toggle('config-active', piezasConfigMode);
    document.getElementById('piezasConfigBanner').style.display = piezasConfigMode ? 'block' : 'none';
    document.getElementById('piezasConfigText').textContent = piezasConfigMode ? 'Listo' : 'Configurar';
    document.getElementById('piezasConfigIcon').textContent = piezasConfigMode ? '✓' : '⚙️';
    document.getElementById('piezasConfigBtn').classList.toggle('active', piezasConfigMode);
}}

function toggleNA(cell) {{
    if (!piezasConfigMode) return;
    const na = getPiezasNA();
    const key = naKey(cell);
    if (cell.classList.contains('miss')) {{
        cell.classList.remove('miss');
        cell.classList.add('na');
        cell.textContent = '✕';
        cell.title = cell.dataset.tipo + ': no aplica';
        na[key] = true;
    }} else if (cell.classList.contains('na')) {{
        cell.classList.remove('na');
        cell.classList.add('miss');
        cell.textContent = '—';
        cell.title = cell.dataset.tipo + ': falta';
        delete na[key];
    }}
    savePiezasNA(na);
    recalcPiezasCoverage();
    recalcResumenCoverage();
    refreshFaltantes();
}}

function recalcResumenCoverage() {{
    const na = getPiezasNA();
    document.querySelectorAll('#resumen .coverage-item[data-eid]').forEach(card => {{
        const eid = card.dataset.eid;
        const nivel = card.dataset.nivel;
        const tr = document.querySelector('#piezas .pieces-table tbody tr[data-eid="' + eid + '"][data-nivel="' + nivel + '"]');
        if (!tr) return;
        let has = 0, applicable = 0;
        tr.querySelectorAll('.piece-cell').forEach(cell => {{
            const key = eid + '_' + nivel + '_' + cell.dataset.tipo;
            if (na[key]) return; // NA — no cuenta en denominador
            applicable++;
            if (cell.classList.contains('has-1') || cell.classList.contains('has-2') || cell.classList.contains('has-3')) has++;
        }});
        const pct = applicable > 0 ? Math.round(has * 100 / applicable) : 100;
        const barColor = pct < 40 ? '#c62828' : pct < 70 ? '#e65100' : '#2e7d32';
        const pctEl = card.querySelector('.coverage-pct');
        const barFill = card.querySelector('.coverage-bar-fill');
        const detail = card.querySelector('.coverage-detail');
        if (pctEl) {{ pctEl.textContent = pct + '%'; pctEl.style.color = barColor; }}
        if (barFill) {{ barFill.style.width = pct + '%'; barFill.style.background = barColor; }}
        if (detail) {{
            const nivelSpan = detail.querySelector('span');
            const nivelStyle = nivelSpan ? nivelSpan.getAttribute('style') : '';
            const naCount = tr.querySelectorAll('.piece-cell').length - applicable;
            const naText = naCount > 0 ? ' · ' + naCount + ' N/A' : '';
            detail.innerHTML = has + ' de ' + applicable + ' piezas' + naText + ' · <span style="' + nivelStyle + '">' + nivel + '</span>';
        }}
    }});
    // Re-ordenar cards por pct ascendente
    const grid = document.querySelector('#resumen .coverage-grid');
    if (grid) {{
        const items = [...grid.querySelectorAll('.coverage-item')];
        items.sort((a, b) => {{
            const pA = parseInt(a.querySelector('.coverage-pct')?.textContent) || 0;
            const pB = parseInt(b.querySelector('.coverage-pct')?.textContent) || 0;
            return pA - pB;
        }});
        items.forEach(el => grid.appendChild(el));
    }}
}}

function recalcPiezasCoverage() {{
    const allTipos = window.__allTipos || [];
    const na = getPiezasNA();
    document.querySelectorAll('#piezas .pieces-table tbody tr').forEach(tr => {{
        const eid = tr.dataset.eid;
        const nivel = tr.dataset.nivel;
        let has = 0, applicable = 0;
        tr.querySelectorAll('.piece-cell').forEach(cell => {{
            const key = eid + '_' + nivel + '_' + cell.dataset.tipo;
            if (na[key]) return; // skip NA
            applicable++;
            if (cell.classList.contains('has-1') || cell.classList.contains('has-2') || cell.classList.contains('has-3')) has++;
        }});
        const pct = applicable > 0 ? Math.round(has / applicable * 100) : 100;
        const barColor = pct < 40 ? '#c62828' : pct < 70 ? '#e65100' : '#2e7d32';
        const barCell = tr.querySelector('.col-bar-cell');
        if (barCell) {{
            barCell.querySelector('.inline-bar-fill').style.width = pct + '%';
            barCell.querySelector('.inline-bar-fill').style.background = barColor;
            barCell.querySelector('.inline-bar-pct').style.color = barColor;
            barCell.querySelector('.inline-bar-pct').textContent = pct + '%';
        }}
    }});
}}

// Apply saved NA config (merged with defaults) and calc coverage on load
document.addEventListener('DOMContentLoaded', () => {{
    const defaults = window.__defaultNA || {{}};
    let na = getPiezasNA();
    // Merge defaults: apply default NA where localStorage has no explicit entry
    let merged = false;
    for (const key in defaults) {{
        if (!(key in na)) {{
            na[key] = true;
            merged = true;
        }}
    }}
    if (merged) savePiezasNA(na);
    document.querySelectorAll('#piezas .pieces-table tbody tr').forEach(tr => {{
        tr.querySelectorAll('.piece-cell.miss').forEach(cell => {{
            const key = naKey(cell);
            if (na[key]) {{
                cell.classList.remove('miss');
                cell.classList.add('na');
                cell.textContent = '✕';
                cell.title = cell.dataset.tipo + ': no aplica';
            }}
        }});
    }});
    recalcPiezasCoverage();
    recalcResumenCoverage();
    // Also refresh Faltantes tab to hide NA pieces
    refreshFaltantes();
}});

function refreshFaltantes() {{
    const na = getPiezasNA();
    document.querySelectorAll('#faltantes .missing-row').forEach(row => {{
        const eid = row.dataset.eid;
        const nivel = row.dataset.nivel;
        let visibleTags = 0;
        row.querySelectorAll('.missing-tag').forEach(tag => {{
            const key = eid + '_' + nivel + '_' + tag.dataset.tipo;
            if (na[key]) {{
                tag.style.display = 'none';
            }} else {{
                tag.style.display = '';
                visibleTags++;
            }}
        }});
        // Hide the entire row if no visible missing tags remain
        row.style.display = visibleTags === 0 ? 'none' : '';
    }});
    // Update nivel section counts
    document.querySelectorAll('#faltantes .section-card').forEach(card => {{
        const visible = card.querySelectorAll('.missing-row:not([style*="display: none"])').length;
        const label = card.querySelector('.count-label');
        if (label) {{
            label.textContent = visible + ' con faltantes';
            if (visible === 0) card.style.display = 'none';
            else card.style.display = '';
        }}
    }});
}}

function filterCatalog() {{
    const q = document.getElementById('catalogSearch').value.toLowerCase();
    const nivel = document.getElementById('catalogNivel').value;
    document.querySelectorAll('#catalogo .school-card').forEach(block => {{
        const school = block.dataset.school.toLowerCase();
        const blockNivel = block.dataset.nivel;
        const products = block.querySelectorAll('.product-card');
        let anyMatch = false;
        products.forEach(row => {{
            const name = (row.dataset.name || '').toLowerCase();
            const match = (school.includes(q) || name.includes(q)) && (!nivel || blockNivel === nivel);
            row.style.display = match ? '' : 'none';
            if (match) anyMatch = true;
        }});
        const schoolMatch = school.includes(q) && (!nivel || blockNivel === nivel);
        block.style.display = (schoolMatch || anyMatch) ? '' : 'none';
        if (anyMatch) block.classList.remove('collapsed');
    }});
    // Hide/show nivel sections
    document.querySelectorAll('#catalogo .nivel-section').forEach(sec => {{
        const sNivel = sec.dataset.nivel;
        if (nivel && sNivel !== nivel) {{ sec.style.display = 'none'; return; }}
        const hasVisible = [...sec.querySelectorAll('.school-card')].some(c => c.style.display !== 'none');
        sec.style.display = hasVisible ? '' : '';
        if (q || nivel) sec.classList.remove('nivel-collapsed');
    }});
}}

function filterTariffs() {{
    const q = document.getElementById('tariffSearch').value.toLowerCase();
    document.querySelectorAll('.tariff-card').forEach(block => {{
        block.style.display = block.dataset.school.toLowerCase().includes(q) ? '' : 'none';
    }});
}}

/* ---- Tariff drill-down ---- */
function toggleDrilldown(row) {{
    const dd = row.querySelector('.drilldown');
    const isOpen = row.classList.contains('expanded');
    // Close all others in same card
    row.closest('.card-body').querySelectorAll('.tariff-product-row.expanded').forEach(r => {{
        if (r !== row) {{ r.classList.remove('expanded'); r.querySelector('.drilldown').style.display = 'none'; }}
    }});
    if (isOpen) {{
        row.classList.remove('expanded');
        dd.style.display = 'none';
    }} else {{
        row.classList.add('expanded');
        dd.style.display = 'block';
    }}
}}

function copySkus(btn) {{
    const table = btn.previousElementSibling;
    const skus = [...table.querySelectorAll('.sku-cell')].map(c => c.textContent).join('\\n');
    navigator.clipboard.writeText(skus).then(() => {{
        const orig = btn.textContent;
        btn.textContent = '✓ Copiados';
        setTimeout(() => btn.textContent = orig, 1500);
    }});
}}

/* ---- Tariff copy/print ---- */
function copyTariff(schoolName) {{
    const data = window.__tariffData[schoolName];
    if (!data) return;
    let text = schoolName + '\\n' + '='.repeat(schoolName.length) + '\\n\\n';
    for (const prod of data.products) {{
        text += prod.tipo + ' — ' + prod.nombre + '\\n';
        for (const v of prod.variants) {{
            text += '  ' + v.t.padEnd(6) + ' $' + v.p.toLocaleString() + '  (stock: ' + v.k + ')\\n';
        }}
        text += '\\n';
    }}
    navigator.clipboard.writeText(text).then(() => {{
        showToast('Tarifario copiado al portapapeles');
    }});
}}

function printTariff(schoolName) {{
    const data = window.__tariffData[schoolName];
    if (!data) return;
    const w = window.open('', '_blank');
    let html = '<html><head><title>Tarifario ' + schoolName + '</title>';
    html += '<style>body{{font-family:sans-serif;font-size:12px;padding:20px}}h1{{font-size:16px;border-bottom:2px solid #87492c;padding-bottom:6px}}';
    html += 'h3{{font-size:13px;color:#87492c;margin:12px 0 4px}}table{{border-collapse:collapse;width:100%;margin-bottom:12px}}';
    html += 'th{{background:#87492c;color:white;padding:4px 8px;font-size:10px;text-align:left}}td{{padding:4px 8px;border-bottom:1px solid #eee;font-size:11px}}';
    html += '.r{{text-align:right}}</style></head><body>';
    html += '<h1>' + schoolName + '</h1>';
    let currentTipo = '';
    for (const prod of data.products) {{
        if (prod.tipo !== currentTipo) {{ currentTipo = prod.tipo; html += '<h3>' + currentTipo + '</h3>'; }}
        html += '<table><thead><tr><th>Producto</th><th>Talla</th><th>Color</th><th class="r">Precio</th><th class="r">Stock</th></tr></thead><tbody>';
        for (const v of prod.variants) {{
            html += '<tr><td>' + prod.nombre + '</td><td>' + v.t + '</td><td>' + v.c + '</td>';
            html += '<td class="r">$' + v.p.toLocaleString() + '</td><td class="r">' + v.k + '</td></tr>';
        }}
        html += '</tbody></table>';
    }}
    html += '</body></html>';
    w.document.write(html);
    w.document.close();
    w.print();
}}

/* ---- Comparison engine ---- */
let compareSlots = [null, null];
let compareMode = false;

function toggleCompareMode() {{
    compareMode = !compareMode;
    const btn = document.getElementById('compareBtnText');
    btn.textContent = compareMode ? 'Cancelar comparación' : 'Comparar escuelas';
    btn.closest('.btn').classList.toggle('active', compareMode);
    document.getElementById('tariffComparePanel').style.display = compareMode ? 'block' : 'none';
    document.querySelectorAll('.compare-btn').forEach(b => b.style.display = compareMode ? 'inline-flex' : 'none');
    if (!compareMode) clearComparison();
}}

function addToCompare(schoolName) {{
    if (compareSlots[0] === schoolName || compareSlots[1] === schoolName) return;
    const slot = compareSlots[0] === null ? 0 : 1;
    if (compareSlots[slot] !== null && slot === 1) return;
    compareSlots[slot] = schoolName;
    const el = document.getElementById('compareSlot' + (slot + 1));
    el.textContent = schoolName;
    el.classList.add('filled');
    el.classList.remove('empty');
    if (compareSlots[0] && compareSlots[1]) runComparison();
}}

function clearCompareSlot(slot) {{
    compareSlots[slot - 1] = null;
    const el = document.getElementById('compareSlot' + slot);
    el.textContent = 'Selecciona escuela...';
    el.classList.remove('filled');
    el.classList.add('empty');
    document.getElementById('compareResult').innerHTML = '';
}}

function clearComparison() {{
    clearCompareSlot(1); clearCompareSlot(2);
}}

function runComparison() {{
    const [s1, s2] = compareSlots;
    if (!s1 || !s2) return;
    const d1 = window.__tariffData[s1], d2 = window.__tariffData[s2];
    if (!d1 || !d2) return;

    // Build product maps by tipo+name for matching
    const map1 = {{}}, map2 = {{}};
    d1.products.forEach(p => {{ map1[p.tipo] = map1[p.tipo] || []; map1[p.tipo].push(p); }});
    d2.products.forEach(p => {{ map2[p.tipo] = map2[p.tipo] || []; map2[p.tipo].push(p); }});
    const allTipos = [...new Set([...Object.keys(map1), ...Object.keys(map2)])];

    let html = '<div class="compare-grid">';
    // Left column
    html += '<div class="compare-col"><h4>' + s1 + '</h4>';
    for (const tipo of allTipos) {{
        const prods = map1[tipo] || [];
        if (prods.length === 0) {{ html += '<div class="compare-prod compare-only">' + tipo + ': —</div>'; continue; }}
        for (const p of prods) {{
            const prices = p.variants.map(v => v.p);
            const lo = Math.min(...prices), hi = Math.max(...prices);
            const priceStr = lo === hi ? '$' + lo.toLocaleString() : '$' + lo.toLocaleString() + '–$' + hi.toLocaleString();
            // Check if same product exists in other school for diff
            const match2 = (map2[tipo] || []).find(p2 => p2.tipo === p.tipo);
            let diffHtml = '';
            if (match2) {{
                const prices2 = match2.variants.map(v => v.p);
                const avg1 = prices.reduce((a,b) => a+b, 0) / prices.length;
                const avg2 = prices2.reduce((a,b) => a+b, 0) / prices2.length;
                const pctDiff = Math.round((avg1 - avg2) / avg2 * 100);
                if (Math.abs(pctDiff) > 3) {{
                    diffHtml = '<span class="compare-diff">' + (pctDiff > 0 ? '+' : '') + pctDiff + '%</span>';
                }}
            }}
            html += '<div class="compare-prod"><span class="compare-prod-name">' + p.nombre + '</span><span class="compare-prod-price">' + priceStr + diffHtml + '</span></div>';
        }}
    }}
    html += '</div>';
    // Right column
    html += '<div class="compare-col"><h4>' + s2 + '</h4>';
    for (const tipo of allTipos) {{
        const prods = map2[tipo] || [];
        if (prods.length === 0) {{ html += '<div class="compare-prod compare-only">' + tipo + ': —</div>'; continue; }}
        for (const p of prods) {{
            const prices = p.variants.map(v => v.p);
            const lo = Math.min(...prices), hi = Math.max(...prices);
            const priceStr = lo === hi ? '$' + lo.toLocaleString() : '$' + lo.toLocaleString() + '–$' + hi.toLocaleString();
            const match1 = (map1[tipo] || []).find(p1 => p1.tipo === p.tipo);
            let diffHtml = '';
            if (match1) {{
                const prices1 = match1.variants.map(v => v.p);
                const avg2 = prices.reduce((a,b) => a+b, 0) / prices.length;
                const avg1 = prices1.reduce((a,b) => a+b, 0) / prices1.length;
                const pctDiff = Math.round((avg2 - avg1) / avg1 * 100);
                if (Math.abs(pctDiff) > 3) {{
                    diffHtml = '<span class="compare-diff">' + (pctDiff > 0 ? '+' : '') + pctDiff + '%</span>';
                }}
            }}
            html += '<div class="compare-prod"><span class="compare-prod-name">' + p.nombre + '</span><span class="compare-prod-price">' + priceStr + diffHtml + '</span></div>';
        }}
    }}
    html += '</div></div>';
    document.getElementById('compareResult').innerHTML = html;
}}

/* ---- Toast notification ---- */
function showToast(msg) {{
    let toast = document.getElementById('toast');
    if (!toast) {{
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1a1a1a;color:white;padding:10px 24px;border-radius:99px;font-size:13px;font-weight:600;z-index:9999;opacity:0;transition:opacity 0.3s;box-shadow:0 4px 12px rgba(0,0,0,0.3)';
        document.body.appendChild(toast);
    }}
    toast.textContent = msg;
    toast.style.opacity = '1';
    setTimeout(() => toast.style.opacity = '0', 2000);
}}

function filterVariants() {{
    const q = document.getElementById('variantSearch').value.toLowerCase();
    const f = document.getElementById('variantFilter').value;
    document.querySelectorAll('#variantTable tbody tr').forEach(row => {{
        const school = (row.dataset.school || '').toLowerCase();
        const name = (row.dataset.name || '').toLowerCase();
        let textMatch = school.includes(q) || name.includes(q);
        let filterMatch = true;
        if (f === 'few') filterMatch = row.classList.contains('row-few');
        if (f === 'inactive') filterMatch = row.classList.contains('row-inactive');
        if (f === 'nostock') filterMatch = row.classList.contains('row-nostock');
        if (f === 'multicolor') filterMatch = row.classList.contains('row-multicolor');
        row.style.display = (textMatch && filterMatch) ? '' : 'none';
    }});
}}

document.addEventListener('DOMContentLoaded', () => {{
    // Collapse all school/tariff cards by default
    document.querySelectorAll('.school-card, .tariff-card').forEach(c => c.classList.add('collapsed'));
    // Collapse all nivel sections by default
    document.querySelectorAll('.nivel-section').forEach(sec => {{
        sec.classList.add('nivel-collapsed');
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

    print("Calculando insights...")
    insights, coverage_data = compute_insights(stats, school_levels, pieces_raw, catalog_rows, catalog_cols, multi_level_ids)

    default_na = compute_default_na(school_levels, pieces_raw)

    print("Generando secciones...")
    resumen = build_resumen(stats, insights, coverage_data)
    pieces = build_pieces(school_levels, pieces_raw, multi_level_ids, default_na)
    tariffs = build_tariffs(catalog_rows, catalog_cols, multi_level_ids)
    catalog = build_catalog(catalog_rows, catalog_cols, multi_level_ids, pieces_raw)
    missing_html = build_missing(school_levels, pieces_raw, multi_level_ids)
    variants = build_variants(catalog_rows, catalog_cols, multi_level_ids)

    html = generate_html(resumen, pieces, tariffs, catalog, missing_html, variants)

    out_path = Path(__file__).resolve().parent.parent / "panel_uniformes.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Panel generado: {out_path}")
    print(f"  Abre: file://{out_path}")


if __name__ == "__main__":
    main()
