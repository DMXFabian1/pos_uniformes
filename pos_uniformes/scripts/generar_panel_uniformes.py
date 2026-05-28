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
    import os, socket as _sock
    _win = "192.168.0.10"
    if not os.getenv("POS_UNIFORMES_DB_HOST"):
        # Primero intentamos localhost; solo si no responde usamos la red (Windows/remoto).
        try:
            s = _sock.create_connection(("127.0.0.1", 5432), timeout=1)
            s.close()
            print("DB: local (Mac)")
        except OSError:
            try:
                s = _sock.create_connection((_win, 5432), timeout=1)
                s.close()
                os.environ["POS_UNIFORMES_DB_HOST"] = _win
                print(f"DB: red ({_win})")
            except OSError:
                print("DB: local (sin red, usando localhost por defecto)")
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
    "Suéter", "Camisa", "Chaleco", "Falda", "Jumper", "Pantalón",
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
    """Generate default NA marks based on actual data.

    Strategy: for each nivel, compute what % of schools carry each piece type.
    If fewer than 50% of schools of a nivel have a piece type, schools that
    don't have it get N/A (it's optional, not missing).  Piece types that ≥50%
    of schools carry are considered standard → missing means a real gap.
    Bachillerato is always fully N/A for missing pieces (each school is unique).
    """
    na = {}

    has_piece: set[tuple] = set()
    for eid, nivel, tipo, cnt in pieces_raw:
        if cnt:
            has_piece.add((eid, nivel, tipo))

    # Group school IDs by nivel
    eids_by_nivel: dict[str, set[int]] = {}
    for sl in school_levels:
        eids_by_nivel.setdefault(sl["nivel_nombre"], set()).add(sl["escuela_id"])

    all_eids_niveles = {(sl["escuela_id"], sl["nivel_nombre"]) for sl in school_levels}

    # Compute adoption rate per (nivel, tipo)
    for nivel, eids in eids_by_nivel.items():
        total = len(eids)
        if total == 0:
            continue

        # Bachillerato: each school is unique, everything missing is N/A
        if nivel == "Bachillerato":
            for eid in eids:
                for tipo in PIEZA_ORDER:
                    if (eid, nivel, tipo) not in has_piece:
                        na[f"{eid}_{nivel}_{tipo}"] = True
            continue

        # For other niveles: check adoption rate
        for tipo in PIEZA_ORDER:
            schools_with = sum(1 for eid in eids if (eid, nivel, tipo) in has_piece)
            adoption_pct = schools_with / total * 100

            # < 50% adoption → optional piece, mark missing as N/A
            if adoption_pct < 50:
                for eid in eids:
                    if (eid, nivel, tipo) not in has_piece:
                        na[f"{eid}_{nivel}_{tipo}"] = True

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
            (SELECT COUNT(*) FROM variante v JOIN producto p ON p.id=v.producto_id
             WHERE v.activo=true AND p.activo=true),
            (SELECT COUNT(*) FROM variante v JOIN producto p ON p.id=v.producto_id
             WHERE v.activo=false AND p.activo=true)
    """)
    stats = dict(zip(["escuelas", "productos", "variantes_activas", "variantes_inactivas"], cur.fetchone()))

    # Stock breakdown
    cur.execute("""
        SELECT
            COALESCE(SUM(v.stock_actual), 0),
            COALESCE(SUM(v.stock_bodega), 0),
            COALESCE(SUM(v.stock_piso), 0),
            COALESCE(SUM(v.stock_actual - v.stock_bodega - v.stock_piso), 0),
            COUNT(*) FILTER (WHERE v.stock_actual = 0),
            COUNT(*) FILTER (WHERE v.stock_actual > 0
                AND (v.stock_actual - v.stock_bodega - v.stock_piso) < COALESCE(v.stock_minimo, 2)),
            COALESCE(SUM(v.stock_actual * v.precio_venta), 0)
        FROM variante v
        JOIN producto p ON p.id = v.producto_id
        WHERE v.activo = true AND p.activo = true
    """)
    row = cur.fetchone()
    stats["stock_total"] = int(row[0])
    stats["stock_bodega"] = int(row[1])
    stats["stock_piso"] = int(row[2])
    stats["stock_tienda"] = int(row[3])
    stats["variantes_sin_stock"] = int(row[4])
    stats["variantes_bajo_min"] = int(row[5])
    stats["valor_inventario"] = float(row[6])

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
            v.precio_venta, v.stock_actual, v.activo AS v_activo,
            v.stock_bodega, v.stock_piso, v.stock_minimo,
            p.escuela_id AS producto_escuela_id
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

    # ── Pieces per school ──────────────────────────────────────────────
    pieces_map = defaultdict(set)
    for eid, nivel, tipo, cnt in pieces_raw:
        pieces_map[(eid, nivel)].add(tipo)

    # Máximo de tipos por nivel (peer comparison).
    max_tipos_por_nivel: dict[str, int] = defaultdict(int)
    for (eid, nivel), tipos in pieces_map.items():
        max_tipos_por_nivel[nivel] = max(max_tipos_por_nivel[nivel], len(tipos))

    # ── Coverage data ──────────────────────────────────────────────────
    coverage_data = []
    for sl in school_levels:
        key = (sl["escuela_id"], sl["nivel_nombre"])
        nivel = sl["nivel_nombre"]
        has = len(pieces_map.get(key, set()))
        nivel_max = max_tipos_por_nivel.get(nivel, 1)
        pct = min(100, round(has / nivel_max * 100)) if nivel_max else 0
        coverage_data.append({"eid": sl["escuela_id"], "name": sl["display_name"], "nivel": nivel, "has": has, "total": nivel_max, "pct": pct})

    n_escuelas = len({c["eid"] for c in coverage_data})
    n_school_levels = len(coverage_data)
    has_multi = n_school_levels > n_escuelas

    low_coverage = sorted([c for c in coverage_data if c["pct"] < 40], key=lambda x: x["pct"])
    mid_coverage = [c for c in coverage_data if 40 <= c["pct"] < 80]
    full_coverage = [c for c in coverage_data if c["pct"] >= 80]
    avg_pct = round(sum(c["pct"] for c in coverage_data) / n_school_levels) if n_school_levels else 0

    # 1) Resumen de cobertura general
    label_suffix = f" ({n_school_levels} escuela-nivel)" if has_multi else ""
    insights.append(("ok", f"Cobertura promedio: {avg_pct}%",
                     f"{len(full_coverage)} completas (≥80%) · {len(mid_coverage)} en progreso · {len(low_coverage)} críticas (<40%){label_suffix}"))

    # 2) Cobertura por nivel educativo
    nivel_stats: dict[str, list[int]] = defaultdict(list)
    for c in coverage_data:
        nivel_stats[c["nivel"]].append(c["pct"])
    nivel_parts = []
    for nivel in NIVEL_ORDER:
        if nivel not in nivel_stats:
            continue
        pcts = nivel_stats[nivel]
        avg = round(sum(pcts) / len(pcts))
        nivel_parts.append(f"{nivel}: {avg}% ({len(pcts)})")
    if nivel_parts:
        insights.append(("info", "Cobertura por nivel", " · ".join(nivel_parts)))

    # 3) Escuelas críticas (<40%) con piezas faltantes
    if low_coverage:
        detail_parts = []
        for c in low_coverage:
            missing = set(PIEZA_ORDER) - pieces_map.get((c["eid"], c["nivel"]), set())
            # Solo mostrar piezas comunes que faltan (las que >30% de escuelas tienen)
            relevant_missing = [p for p in PIEZA_ORDER if p in missing]
            miss_str = ", ".join(relevant_missing[:5])
            if len(relevant_missing) > 5:
                miss_str += f" (+{len(relevant_missing)-5})"
            detail_parts.append(f"{c['name']} ({c['pct']}%) — faltan: {miss_str}")
        insights.append(("warn", f"{len(low_coverage)} escuelas con menos del 40% de piezas",
                         "\n".join(detail_parts)))

    # 4) Piezas menos cubiertas (oportunidad de mejora)
    all_school_levels = {(c["eid"], c["nivel"]) for c in coverage_data}
    piece_coverage: dict[str, int] = {}
    for pieza in PIEZA_ORDER:
        count = sum(1 for key in all_school_levels if pieza in pieces_map.get(key, set()))
        piece_coverage[pieza] = count
    # Mostrar piezas que tienen cobertura <60% de escuelas
    low_pieces = [(p, cnt) for p, cnt in piece_coverage.items() if cnt < n_school_levels * 0.6]
    low_pieces.sort(key=lambda x: x[1])
    if low_pieces:
        detail = " · ".join(f"{p} ({cnt}/{n_school_levels})" for p, cnt in low_pieces)
        insights.append(("info", "Piezas con menor cobertura entre escuelas", detail))

    # ── Stock analysis ─────────────────────────────────────────────────
    stock_by_product = defaultdict(lambda: {"stock": 0, "variants": 0, "name": "", "school": ""})
    zero_stock_products = 0
    total_products = 0
    zero_stock_schools: set[str] = set()
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
            zero_stock_schools.add(p["school"])

    if zero_stock_products > 0:
        pct = round(zero_stock_products / total_products * 100)
        with_stock = total_products - zero_stock_products
        insights.append(("alert",
                         f"{zero_stock_products} de {total_products} productos sin stock ({pct}%)",
                         f"{with_stock} productos con inventario · {len(zero_stock_schools)} escuelas afectadas"))

    return insights, coverage_data


# ---------------------------------------------------------------------------
# HTML Section builders
# ---------------------------------------------------------------------------

def build_resumen(stats, insights, coverage_data):
    niveles = stats["por_nivel"]
    total_escuelas = stats["escuelas"]
    h = []

    # ── Row 1: KPIs principales ──
    valor_inv = stats["valor_inventario"]
    valor_str = f"${valor_inv/1_000_000:.1f}M" if valor_inv >= 1_000_000 else f"${valor_inv/1000:.0f}K" if valor_inv >= 1000 else f"${valor_inv:,.0f}"
    h.append('<div class="res-kpi-row">')
    kpis = [
        (f'{stats["escuelas"]}', "Escuelas", "school", "activas"),
        (f'{stats["productos"]:,}', "Productos", "product", "activos"),
        (f'{stats["stock_tienda"]:,}', "Piezas en tienda", "stock", f'{stats["stock_total"]:,} total'),
        (valor_str, "Valor inventario", "valor", "precio de venta"),
    ]
    for val, label, cls, sub in kpis:
        h.append(f'<div class="res-kpi {cls}"><div class="res-kpi-val">{val}</div>'
                 f'<div class="res-kpi-label">{label}</div>'
                 f'<div class="res-kpi-sub">{sub}</div></div>')
    h.append('</div>')

    # ── Row 2: Stock por ubicación + Salud inventario ──
    h.append('<div class="res-two-col">')

    # -- Col A: Stock por ubicación (stacked bar) --
    st = stats["stock_tienda"]
    sp = stats["stock_piso"]
    sb = stats["stock_bodega"]
    stotal = stats["stock_total"] or 1
    pct_t = round(st / stotal * 100)
    pct_p = round(sp / stotal * 100)
    pct_b = round(sb / stotal * 100)
    h.append('<div class="res-card">')
    h.append('<div class="res-card-title">Stock por ubicación</div>')
    h.append(f'<div class="res-stacked-bar">'
             f'<div class="res-sb-seg tienda" style="width:{pct_t}%" title="Tienda: {st:,}"></div>'
             f'<div class="res-sb-seg piso" style="width:{pct_p}%" title="Piso: {sp:,}"></div>'
             f'<div class="res-sb-seg bodega" style="width:{pct_b}%" title="Almacén: {sb:,}"></div>'
             f'</div>')
    h.append('<div class="res-legend">')
    h.append(f'<span class="res-leg-item"><span class="res-leg-dot tienda"></span>Tienda <b>{st:,}</b> ({pct_t}%)</span>')
    h.append(f'<span class="res-leg-item"><span class="res-leg-dot piso"></span>Piso <b>{sp:,}</b> ({pct_p}%)</span>')
    h.append(f'<span class="res-leg-item"><span class="res-leg-dot bodega"></span>Almacén <b>{sb:,}</b> ({pct_b}%)</span>')
    h.append('</div></div>')

    # -- Col B: Salud del inventario --
    v_activas = stats["variantes_activas"]
    v_sin = stats["variantes_sin_stock"]
    v_bajo = stats["variantes_bajo_min"]
    v_ok = v_activas - v_sin - v_bajo
    pct_ok = round(v_ok / v_activas * 100) if v_activas else 0
    pct_sin = round(v_sin / v_activas * 100) if v_activas else 0
    pct_bajo = round(v_bajo / v_activas * 100) if v_activas else 0
    h.append('<div class="res-card">')
    h.append('<div class="res-card-title">Salud del inventario</div>')
    h.append(f'<div class="res-stacked-bar">'
             f'<div class="res-sb-seg ok" style="width:{pct_ok}%" title="OK: {v_ok:,}"></div>'
             f'<div class="res-sb-seg bajo" style="width:{pct_bajo}%" title="Bajo mínimo: {v_bajo:,}"></div>'
             f'<div class="res-sb-seg sin" style="width:{pct_sin}%" title="Sin stock: {v_sin:,}"></div>'
             f'</div>')
    h.append('<div class="res-legend">')
    h.append(f'<span class="res-leg-item"><span class="res-leg-dot ok"></span>OK <b>{v_ok:,}</b></span>')
    h.append(f'<span class="res-leg-item"><span class="res-leg-dot bajo"></span>Bajo mínimo <b>{v_bajo:,}</b></span>')
    h.append(f'<span class="res-leg-item"><span class="res-leg-dot sin"></span>Sin stock <b>{v_sin:,}</b></span>')
    h.append('</div></div>')
    h.append('</div>')  # close res-two-col

    # ── Row 3: Cobertura por nivel + Escuelas por nivel ──
    h.append('<div class="res-two-col">')

    # -- Col A: Cobertura por nivel --
    nivel_stats: dict[str, list[int]] = defaultdict(list)
    for c in coverage_data:
        nivel_stats[c["nivel"]].append(c["pct"])
    low_coverage = [c for c in coverage_data if c["pct"] < 40]
    full_coverage = [c for c in coverage_data if c["pct"] >= 80]
    avg_pct = round(sum(c["pct"] for c in coverage_data) / len(coverage_data)) if coverage_data else 0

    h.append('<div class="res-card">')
    h.append(f'<div class="res-card-title">Cobertura de piezas <span class="res-card-badge" style="background:{"var(--green-bg);color:var(--green)" if avg_pct >= 70 else "var(--orange-bg);color:var(--orange)" if avg_pct >= 40 else "var(--red-bg);color:var(--red)"}"">{avg_pct}% promedio</span></div>')
    for nivel in NIVEL_ORDER:
        if nivel not in nivel_stats:
            continue
        pcts = nivel_stats[nivel]
        avg = round(sum(pcts) / len(pcts))
        color = NIVEL_COLORS.get(nivel, "#999")
        bar_color = "#c62828" if avg < 40 else "#e65100" if avg < 70 else "#2e7d32"
        h.append(f'<div class="res-cov-row">'
                 f'<span class="res-cov-nivel"><span class="nivel-dot" style="background:{color}"></span>{nivel}</span>'
                 f'<div class="res-cov-bar"><div class="res-cov-fill" style="width:{avg}%;background:{bar_color}"></div></div>'
                 f'<span class="res-cov-pct" style="color:{bar_color}">{avg}%</span>'
                 f'</div>')
    h.append(f'<div class="res-cov-summary">{len(full_coverage)} completas · {len(low_coverage)} críticas</div>')
    h.append('</div>')

    # -- Col B: Distribución por nivel --
    h.append('<div class="res-card">')
    h.append('<div class="res-card-title">Escuelas por nivel</div>')
    for nivel in NIVEL_ORDER:
        cnt = niveles.get(nivel, 0)
        pct = round(cnt / total_escuelas * 100) if total_escuelas else 0
        color = NIVEL_COLORS.get(nivel, "#999")
        h.append(f'<div class="res-cov-row">'
                 f'<span class="res-cov-nivel"><span class="nivel-dot" style="background:{color}"></span>{nivel}</span>'
                 f'<div class="res-cov-bar"><div class="res-cov-fill" style="width:{pct}%;background:{color}"></div></div>'
                 f'<span class="res-cov-pct" style="color:{color}">{cnt}</span>'
                 f'</div>')
    h.append('</div>')
    h.append('</div>')  # close res-two-col

    # ── Row 4: Alertas (solo si hay) ──
    alerts = [i for i in insights if i[0] in ("warn", "alert")]
    if alerts:
        h.append('<div class="res-card res-alerts">')
        h.append('<div class="res-card-title">⚠ Alertas</div>')
        for kind, title, detail in alerts:
            cls = "res-alert-warn" if kind == "warn" else "res-alert-danger"
            h.append(f'<div class="res-alert {cls}">')
            h.append(f'<div class="res-alert-title">{_esc(title)}</div>')
            if detail:
                if "\n" in detail:
                    lines = detail.split("\n")
                    h.append('<div class="res-alert-detail">')
                    for line in lines[:5]:
                        h.append(f'<div class="res-alert-line">{_esc(line)}</div>')
                    if len(lines) > 5:
                        h.append(f'<div class="res-alert-line" style="color:var(--text-muted)">… y {len(lines)-5} más</div>')
                    h.append('</div>')
                else:
                    h.append(f'<div class="res-alert-detail">{_esc(detail)}</div>')
            h.append('</div>')
        h.append('</div>')

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





def build_variants(catalog_rows, catalog_cols, multi_level_ids):
    col_idx = {c: i for i, c in enumerate(catalog_cols)}

    # Build product data with per-talla stock
    _SIEMPRE_VIRTUALES = {"Pants 3pz", "Chamarra"}
    _VIRTUALES_SI_NO_ESCUELA = {"Jumper", "Falda"}
    schools: dict[str, dict] = OrderedDict()
    for row in catalog_rows:
        eid = row[col_idx["escuela_id"]]
        ename = row[col_idx["escuela"]]
        nivel = row[col_idx["nivel"]]
        display = f"{ename} {nivel}" if eid in multi_level_ids else ename
        pid = row[col_idx["producto_id"]]
        vid = row[col_idx["variante_id"]]

        if display not in schools:
            schools[display] = {"nivel": nivel, "eid": eid, "products": OrderedDict()}
        if pid not in schools[display]["products"]:
            schools[display]["products"][pid] = {
                "nombre": row[col_idx["nombre_base"]],
                "tipo": row[col_idx["tipo_pieza"]],
                "escuela_directa": row[col_idx["producto_escuela_id"]] is not None,
                "tallas": [],  # list of {talla, stock_tienda, stock_piso, stock_bodega, estado}
                "stock_total": 0,
                "agotadas": 0,
                "bajo_min": 0,
            }
        if vid is None or not row[col_idx["v_activo"]]:
            continue
        tipo_pieza = row[col_idx["tipo_pieza"]]
        if tipo_pieza in _SIEMPRE_VIRTUALES:
            continue
        if tipo_pieza in _VIRTUALES_SI_NO_ESCUELA and row[col_idx["producto_escuela_id"]] is None:
            continue

        p = schools[display]["products"][pid]
        t = row[col_idx["talla"]] or "-"
        stock_actual = row[col_idx["stock_actual"]] or 0
        stock_bodega = row[col_idx.get("stock_bodega", -1)] if "stock_bodega" in col_idx else 0
        stock_piso = row[col_idx.get("stock_piso", -1)] if "stock_piso" in col_idx else 0
        stock_minimo = row[col_idx.get("stock_minimo", -1)] if "stock_minimo" in col_idx else None
        stock_tienda = stock_actual - (stock_bodega or 0) - (stock_piso or 0)
        min_val = int(stock_minimo) if stock_minimo is not None else 2

        if stock_tienda <= 0:
            estado = "agotado"
            p["agotadas"] += 1
        elif stock_tienda < min_val:
            estado = "bajo"
            p["bajo_min"] += 1
        else:
            estado = "ok"

        p["tallas"].append({
            "talla": t,
            "stock_tienda": stock_tienda,
            "stock_piso": stock_piso or 0,
            "stock_bodega": stock_bodega or 0,
            "estado": estado,
        })
        p["stock_total"] += stock_tienda

    # Remove virtual/empty products, sort tallas
    def _es_visible(p):
        if not p["tallas"]:
            return False
        if p["tipo"] in _SIEMPRE_VIRTUALES:
            return False
        if p["tipo"] in _VIRTUALES_SI_NO_ESCUELA and not p["escuela_directa"]:
            return False
        return True

    for sdata in schools.values():
        sdata["products"] = {
            pid: p for pid, p in sdata["products"].items()
            if _es_visible(p)
        }
        for p in sdata["products"].values():
            p["tallas"].sort(key=lambda x: talla_sort_key(x["talla"]))
            p["n_tallas"] = len(p["tallas"])

    # Global stats
    total_tallas = 0
    tallas_agotadas = 0
    tallas_bajo = 0
    productos_criticos = 0
    total_stock = 0
    for sdata in schools.values():
        for p in sdata["products"].values():
            total_tallas += p["n_tallas"]
            tallas_agotadas += p["agotadas"]
            tallas_bajo += p["bajo_min"]
            total_stock += p["stock_total"]
            if p["agotadas"] > 0:
                productos_criticos += 1

    cobertura_pct = round((total_tallas - tallas_agotadas) / total_tallas * 100) if total_tallas > 0 else 0

    h = []

    # ── Stats bar ──
    _cob_color = "var(--green)" if cobertura_pct >= 80 else "var(--orange)" if cobertura_pct >= 50 else "var(--red)"
    h.append('<div class="disp-stats">')
    h.append(f'<div class="disp-stat agotado"><div class="disp-stat-val">{tallas_agotadas}</div><div class="disp-stat-label">Agotadas</div></div>')
    h.append(f'<div class="disp-stat bajo"><div class="disp-stat-val">{tallas_bajo}</div><div class="disp-stat-label">Bajo mínimo</div></div>')
    h.append(f'<div class="disp-stat critico"><div class="disp-stat-val">{productos_criticos}</div><div class="disp-stat-label">Con faltantes</div></div>')
    h.append(f'<div class="disp-stat cob"><div class="disp-stat-val" style="color:{_cob_color}">{cobertura_pct}%</div><div class="disp-stat-label">Cobertura</div></div>')
    h.append('</div>')

    # ── Filters ──
    h.append('''<div class="disp-filter-bar">
        <div class="disp-search-wrap">
            <span class="disp-search-icon">🔍</span>
            <input type="text" id="variantSearch" placeholder="Buscar producto, escuela..." class="disp-search" oninput="filterDisponibilidad()">
        </div>
        <select id="variantFilter" class="disp-select" onchange="filterDisponibilidad()">
            <option value="">Todos</option>
            <option value="critico">Con agotadas</option>
            <option value="bajo">Bajo mínimo</option>
            <option value="ok">Completo</option>
        </select>
    </div>''')

    # ── School sections ──
    schools_sorted = sorted(
        schools.items(),
        key=lambda x: (NIVEL_ORDER.index(x[1]["nivel"]) if x[1]["nivel"] in NIVEL_ORDER else 99, x[0]),
    )

    for school_name, sdata in schools_sorted:
        products_sorted = sorted(
            sdata["products"].values(),
            key=lambda p: (PIEZA_ORDER.index(p["tipo"]) if p["tipo"] in PIEZA_ORDER else 99, p["nombre"]),
        )
        n_prods = len(products_sorted)
        sch_agotadas = sum(p["agotadas"] for p in products_sorted)
        sch_bajo = sum(p["bajo_min"] for p in products_sorted)
        sch_total_tallas = sum(p["n_tallas"] for p in products_sorted)
        sch_ok_tallas = sch_total_tallas - sum(p["agotadas"] for p in products_sorted) - sum(p["bajo_min"] for p in products_sorted)
        sch_pct = round(sch_ok_tallas / sch_total_tallas * 100) if sch_total_tallas else 100
        nivel_color = NIVEL_COLORS.get(sdata["nivel"], "#999")

        # Status chips
        chips = ""
        if sch_agotadas > 0:
            chips += f'<span class="disp-sch-chip agotado">{sch_agotadas} agotada{"s" if sch_agotadas != 1 else ""}</span>'
        if sch_bajo > 0:
            chips += f'<span class="disp-sch-chip bajo">{sch_bajo} bajo mín</span>'
        if not chips:
            chips = '<span class="disp-sch-chip ok">✓ Completo</span>'

        h.append(f'<div class="disp-school-group" data-school="{_esc(school_name)}">')
        h.append(f'<div class="disp-sch-header" onclick="this.parentElement.classList.toggle(\'collapsed\')">')
        h.append(f'<span class="disp-chevron">▾</span>')
        h.append(f'<span class="nivel-dot" style="background:{nivel_color}"></span>')
        h.append(f'<span class="disp-sch-name">{_esc(school_name)}</span>')
        h.append(f'{chips}')
        h.append(f'<span class="disp-sch-meta">{n_prods} prod · {sch_total_tallas} tallas</span>')
        # Mini progress bar
        bar_color = "#c62828" if sch_pct < 50 else "#e65100" if sch_pct < 80 else "#2e7d32"
        h.append(f'<div class="disp-sch-bar"><div class="disp-sch-bar-fill" style="width:{sch_pct}%;background:{bar_color}"></div></div>')
        h.append(f'<span class="disp-sch-pct" style="color:{bar_color}">{sch_pct}%</span>')
        h.append('</div>')
        h.append('<div class="disp-school-body">')

        for p in products_sorted:
            if p["agotadas"] > 0:
                status_cls = "disp-critico"
            elif p["bajo_min"] > 0:
                status_cls = "disp-bajo"
            else:
                status_cls = "disp-ok"

            h.append(f'<div class="disp-product-card {status_cls}" data-name="{_esc(p["nombre"])}" data-status="{status_cls}">')
            h.append(f'<div class="disp-prod-header">')
            h.append(f'<span class="disp-tipo">{_esc(p["tipo"])}</span>')
            h.append(f'<span class="disp-prod-name">{_esc(p["nombre"])}</span>')
            # Status summary
            if p["agotadas"] > 0:
                h.append(f'<span class="disp-prod-status agotado">{p["agotadas"]}/{p["n_tallas"]} agotadas</span>')
            elif p["bajo_min"] > 0:
                h.append(f'<span class="disp-prod-status bajo">{p["bajo_min"]} bajo mín</span>')
            else:
                h.append(f'<span class="disp-prod-status ok">✓</span>')
            h.append('</div>')
            # Talla grid
            h.append('<div class="disp-talla-grid">')
            for t in p["tallas"]:
                cls = f"disp-talla disp-talla-{t['estado']}"
                tooltip = f'{t["talla"]}: {t["stock_tienda"]} en tienda'
                if t["stock_piso"] > 0:
                    tooltip += f', {t["stock_piso"]} en piso'
                if t["stock_bodega"] > 0:
                    tooltip += f', {t["stock_bodega"]} en almacén'
                h.append(f'<div class="{cls}" title="{_esc(tooltip)}">')
                h.append(f'<span class="disp-talla-label">{_esc(t["talla"])}</span>')
                h.append(f'<span class="disp-talla-stock">{t["stock_tienda"]}</span>')
                h.append('</div>')
            h.append('</div>')
            h.append('</div>')

        h.append('</div></div>')

    return "\n".join(h)


def build_conteo(school_levels):
    """Genera la pestaña de conteo de inventario (interactiva via QWebChannel)."""
    seen = set()
    schools = []
    for sl in school_levels:
        eid = sl["escuela_id"]
        if eid not in seen:
            seen.add(eid)
            schools.append((eid, sl["escuela_nombre"]))
    schools.sort(key=lambda x: x[1])

    h = []

    # Fallback for browser mode
    h.append('<div id="conteo-fallback" style="display:none">')
    h.append('<div class="section-card" style="text-align:center;padding:40px">')
    h.append('<h3 style="color:var(--text-muted)">Conteo de inventario</h3>')
    h.append('<p style="color:var(--text-muted)">Esta funcionalidad solo esta disponible dentro de la aplicacion POS.</p>')
    h.append('</div></div>')

    h.append('<div id="conteo-app">')

    # ── Top controls ──
    h.append('<div class="filter-bar" style="flex-wrap:wrap;gap:10px;align-items:center">')
    h.append('<div style="display:flex;align-items:center;gap:8px">')
    h.append('<label style="font-weight:600;font-size:13px">Escuela:</label>')
    h.append('<select id="conteo-escuela" onchange="conteoLoadEscuela()" class="filter-select" style="min-width:220px">')
    h.append('<option value="">— Seleccionar escuela —</option>')
    for eid, ename in schools:
        h.append(f'<option value="{eid}">{_esc(ename)}</option>')
    h.append('</select>')
    h.append('</div>')
    h.append('<div style="display:flex;align-items:center;gap:8px">')
    h.append('<label style="font-weight:600;font-size:13px">Contado por:</label>')
    h.append('<input type="text" id="conteo-por" placeholder="Nombre" class="search-box" style="min-width:140px;flex:0">')
    h.append('</div>')
    h.append('<button class="btn" onclick="conteoGuardar()" id="conteo-guardar-btn" disabled style="margin-left:auto">Guardar conteo</button>')
    h.append('</div>')

    # ── Sub-tabs ──
    h.append('<div id="conteo-subtabs" style="display:none;margin-bottom:14px;gap:6px">')
    h.append('<button class="btn btn-sm btn-outline active" onclick="conteoShowSubtab(\'contar\')" data-subtab="contar">Contar</button>')
    h.append('<button class="btn btn-sm btn-outline" onclick="conteoShowSubtab(\'pendientes\')" data-subtab="pendientes">Pendientes <span id="conteo-pendientes-badge" style="display:none;background:var(--red);color:#fff;border-radius:99px;padding:0 6px;font-size:10px;margin-left:4px"></span></button>')
    h.append('<button class="btn btn-sm btn-outline" onclick="conteoShowSubtab(\'historial\')" data-subtab="historial">Historial</button>')
    h.append('</div>')

    # ── Estado card with progress ──
    h.append('<div id="conteo-estado" class="section-card" style="display:none">')
    h.append('<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">')
    h.append('<div id="conteo-estado-info" style="flex:1;font-size:13px"></div>')
    h.append('<div style="display:flex;align-items:center;gap:8px">')
    h.append('<label style="font-size:12px;color:var(--text-muted)">Vigencia (dias):</label>')
    h.append('<input type="number" id="conteo-vigencia" min="1" max="365" value="90" style="width:60px;padding:4px;border-radius:var(--radius-xs);border:1px solid var(--border);font-size:12px;background:var(--card-bg);color:var(--text)">')
    h.append('<button class="btn btn-sm btn-outline" onclick="conteoGuardarConfig()" style="font-size:11px;padding:3px 8px">Guardar</button>')
    h.append('</div>')
    h.append('</div>')
    # Session progress bar
    h.append('<div id="conteo-progress" style="margin-top:12px">')
    h.append('<div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">')
    h.append('<span id="conteo-progress-text" style="color:var(--text-muted)">0 de 0 productos contados</span>')
    h.append('<span id="conteo-progress-pct" style="font-weight:700;color:var(--brand)">0%</span>')
    h.append('</div>')
    h.append('<div style="height:8px;width:100%;background:var(--border-light);border-radius:99px;overflow:hidden">')
    h.append('<div id="conteo-progress-fill" style="height:100%;background:var(--brand);width:0%;transition:width 0.4s cubic-bezier(0.4,0,0.2,1);border-radius:99px"></div>')
    h.append('</div>')
    h.append('</div>')
    h.append('</div>')

    # ── Panel: Contar ──
    h.append('<div id="conteo-panel-contar" class="conteo-subtab-panel" style="display:none">')
    # Search & filters
    h.append('<div class="filter-bar" style="gap:8px;margin-bottom:14px">')
    h.append('<input type="text" id="conteo-search" placeholder="Buscar producto o SKU..." class="search-box" oninput="conteoFilterProducts()">')
    h.append('<button class="btn btn-sm btn-outline active" onclick="conteoSetFilter(\'todos\',this)" data-filter="todos">Todos</button>')
    h.append('<button class="btn btn-sm btn-outline" onclick="conteoSetFilter(\'sincontar\',this)" data-filter="sincontar">Sin contar</button>')
    h.append('<button class="btn btn-sm btn-outline" onclick="conteoSetFilter(\'diferencia\',this)" data-filter="diferencia">Con diferencia</button>')
    h.append('</div>')
    # Adjust prompt (hidden)
    h.append('<div id="conteo-adjust-prompt" class="section-card conteo-adjust-prompt" style="display:none">')
    h.append('<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">')
    h.append('<span id="conteo-adjust-msg" style="font-size:13px"></span>')
    h.append('<button class="btn btn-sm" onclick="conteoApplyAdjustments()">Si, ajustar stock</button>')
    h.append('<button class="btn btn-sm btn-outline" onclick="conteoDismissPrompt()">No, ver pendientes</button>')
    h.append('</div>')
    h.append('</div>')
    # Product cards container
    h.append('<div id="conteo-products-container"></div>')
    h.append('</div>')

    # ── Panel: Pendientes ──
    h.append('<div id="conteo-panel-pendientes" class="conteo-subtab-panel" style="display:none">')
    h.append('<div class="section-card" style="padding:20px">')
    # Toolbar
    h.append('<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">')
    h.append('<div style="display:flex;align-items:center;gap:10px">')
    h.append('<h3 style="margin:0;font-size:17px">Conteos pendientes de ajuste</h3>')
    h.append('<span id="conteo-pendientes-count" class="meta-chip" style="background:var(--red-bg,#fbe9e7);color:var(--red)"></span>')
    h.append('</div>')
    h.append('<div style="display:flex;gap:8px;align-items:center">')
    h.append('<label style="font-size:13px;display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" id="conteo-select-all" onchange="conteoToggleAll(this)"> Seleccionar todos</label>')
    h.append('<button class="btn btn-sm" onclick="conteoConfirmarAjustes()" id="conteo-ajustar-btn" disabled style="white-space:nowrap">Confirmar seleccionados</button>')
    h.append('</div>')
    h.append('</div>')
    # Cards container
    h.append('<div id="conteo-pendientes-container"></div>')
    h.append('<div id="conteo-pendientes-empty" style="display:none;text-align:center;padding:40px;color:var(--text-muted)">')
    h.append('<span style="font-size:32px">✅</span><p style="margin-top:8px">Sin conteos pendientes de ajuste</p></div>')
    h.append('</div>')
    h.append('</div>')

    # ── Panel: Historial ──
    h.append('<div id="conteo-panel-historial" class="conteo-subtab-panel" style="display:none">')
    h.append('<div class="section-card" style="padding:20px">')
    h.append('<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">')
    h.append('<h3 style="margin:0;font-size:17px">Historial de conteos</h3>')
    h.append('<span id="conteo-historial-count" class="meta-chip" style="color:var(--text-muted)"></span>')
    h.append('</div>')
    h.append('<div id="conteo-historial-container"></div>')
    h.append('<div id="conteo-historial-empty" style="display:none;text-align:center;padding:40px;color:var(--text-muted)">')
    h.append('<span style="font-size:32px">📋</span><p style="margin-top:8px">Sin historial de conteos</p></div>')
    h.append('</div>')
    h.append('</div>')

    h.append('</div>')  # close conteo-app
    return "\n".join(h)


# ---------------------------------------------------------------------------
# Full HTML
# ---------------------------------------------------------------------------

def generate_html(resumen, pieces, tariffs, variants, conteo):
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
/* ============ RESUMEN ============ */
.res-kpi-row {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:14px; margin-bottom:16px; }}
.res-kpi {{ background:var(--card-bg); border-radius:var(--radius); padding:18px 20px;
    box-shadow:var(--shadow); border-left:4px solid var(--border); }}
.res-kpi.school {{ border-left-color:var(--purple); }}
.res-kpi.product {{ border-left-color:var(--blue); }}
.res-kpi.stock {{ border-left-color:var(--green); }}
.res-kpi.valor {{ border-left-color:var(--brand); }}
.res-kpi-val {{ font-size:28px; font-weight:800; letter-spacing:-1px; }}
.res-kpi.school .res-kpi-val {{ color:var(--purple); }}
.res-kpi.product .res-kpi-val {{ color:var(--blue); }}
.res-kpi.stock .res-kpi-val {{ color:var(--green); }}
.res-kpi.valor .res-kpi-val {{ color:var(--brand); }}
.res-kpi-label {{ font-size:13px; font-weight:600; color:var(--text-muted); margin-top:2px; }}
.res-kpi-sub {{ font-size:11px; color:var(--text-muted); }}

.res-two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:16px; }}
.res-card {{ background:var(--card-bg); border-radius:var(--radius); padding:18px 20px; box-shadow:var(--shadow); }}
.res-card-title {{ font-weight:700; font-size:14px; margin-bottom:14px; display:flex; align-items:center; gap:8px; }}
.res-card-badge {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:99px; }}

.res-stacked-bar {{ display:flex; height:28px; border-radius:var(--radius-sm); overflow:hidden; margin-bottom:10px; }}
.res-sb-seg {{ transition:width 0.5s ease; min-width:2px; }}
.res-sb-seg.tienda {{ background:var(--green); }}
.res-sb-seg.piso {{ background:var(--orange); }}
.res-sb-seg.bodega {{ background:var(--blue); }}
.res-sb-seg.ok {{ background:var(--green); }}
.res-sb-seg.bajo {{ background:var(--orange); }}
.res-sb-seg.sin {{ background:var(--red); }}

.res-legend {{ display:flex; gap:16px; flex-wrap:wrap; }}
.res-leg-item {{ font-size:12px; color:var(--text-muted); display:flex; align-items:center; gap:4px; }}
.res-leg-item b {{ color:var(--text); }}
.res-leg-dot {{ width:10px; height:10px; border-radius:50%; flex-shrink:0; }}
.res-leg-dot.tienda {{ background:var(--green); }}
.res-leg-dot.piso {{ background:var(--orange); }}
.res-leg-dot.bodega {{ background:var(--blue); }}
.res-leg-dot.ok {{ background:var(--green); }}
.res-leg-dot.bajo {{ background:var(--orange); }}
.res-leg-dot.sin {{ background:var(--red); }}

.res-cov-row {{ display:flex; align-items:center; gap:10px; margin-bottom:8px; }}
.res-cov-nivel {{ display:flex; align-items:center; gap:6px; font-size:13px; font-weight:600; min-width:110px; }}
.res-cov-bar {{ flex:1; height:8px; background:var(--border-light); border-radius:99px; overflow:hidden; }}
.res-cov-fill {{ height:100%; border-radius:99px; transition:width 0.5s ease; }}
.res-cov-pct {{ font-weight:700; font-size:13px; min-width:40px; text-align:right; }}
.res-cov-summary {{ font-size:12px; color:var(--text-muted); margin-top:8px; padding-top:8px;
    border-top:1px solid var(--border-light); }}

.res-alerts {{ margin-bottom:0; }}
.res-alert {{ padding:10px 14px; border-radius:var(--radius-sm); margin-bottom:6px; }}
.res-alert-warn {{ background:var(--orange-bg); }}
.res-alert-danger {{ background:var(--red-bg); }}
.res-alert-title {{ font-weight:600; font-size:13px; }}
.res-alert-detail {{ font-size:12px; color:var(--text-muted); margin-top:4px; }}
.res-alert-line {{ padding-left:4px; border-left:2px solid rgba(0,0,0,.1); margin-bottom:2px; }}

@media (max-width: 800px) {{
    .res-kpi-row {{ grid-template-columns:repeat(2, 1fr); }}
    .res-two-col {{ grid-template-columns:1fr; }}
}}

/* legacy KPI classes kept for other sections */
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
.insight-detail-list {{ display: flex; flex-direction: column; gap: 3px; margin-top: 4px; }}
.insight-detail-item {{ font-size: 12px; color: var(--text-muted); padding-left: 4px; border-left: 2px solid rgba(0,0,0,.1); }}

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
.piece-cell.miss {{ color: var(--red); font-weight: 400; cursor: pointer; }}
.piece-cell.miss:hover {{ background: color-mix(in srgb, var(--orange) 15%, transparent); }}
.piece-cell.na {{ color: var(--text-muted); font-weight: 400; opacity: 0.4; cursor: pointer; font-size: 11px; }}
.piece-cell.na:hover {{ background: color-mix(in srgb, var(--blue) 15%, transparent); }}
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

/* (Faltantes tab removed — merged into Piezas) */

/* ============ DISPONIBILIDAD ============ */
.disp-stats {{ display:flex; gap:10px; margin-bottom:16px; }}
.disp-stat {{ flex:1; background:var(--card-bg); border-radius:var(--radius); padding:14px 16px;
    box-shadow:var(--shadow); text-align:center; border-bottom:3px solid transparent; }}
.disp-stat.agotado {{ border-bottom-color:var(--red); }}
.disp-stat.bajo {{ border-bottom-color:var(--orange); }}
.disp-stat.critico {{ border-bottom-color:var(--red); }}
.disp-stat.cob {{ border-bottom-color:var(--brand); }}
.disp-stat-val {{ font-size:22px; font-weight:800; letter-spacing:-0.5px; }}
.disp-stat.agotado .disp-stat-val {{ color:var(--red); }}
.disp-stat.bajo .disp-stat-val {{ color:var(--orange); }}
.disp-stat.critico .disp-stat-val {{ color:var(--red); }}
.disp-stat-label {{ font-size:11px; font-weight:600; color:var(--text-muted); margin-top:2px; text-transform:uppercase; letter-spacing:.3px; }}

.disp-filter-bar {{ display:flex; gap:10px; margin-bottom:16px; align-items:center; }}
.disp-search-wrap {{ flex:1; position:relative; }}
.disp-search-icon {{ position:absolute; left:12px; top:50%; transform:translateY(-50%); font-size:13px; opacity:.5; }}
.disp-search {{ width:100%; padding:10px 12px 10px 34px; border:1px solid var(--border); border-radius:var(--radius);
    font-size:13px; background:var(--card-bg); color:var(--text); outline:none; }}
.disp-search:focus {{ border-color:var(--brand); box-shadow:0 0 0 3px rgba(135,73,44,.1); }}
.disp-select {{ padding:10px 14px; border:1px solid var(--border); border-radius:var(--radius);
    font-size:13px; background:var(--card-bg); color:var(--text); min-width:140px; cursor:pointer; }}

.disp-school-group {{ background:var(--card-bg); border-radius:var(--radius); box-shadow:var(--shadow);
    margin-bottom:10px; overflow:hidden; }}
.disp-school-group.collapsed .disp-school-body {{ display:none; }}
.disp-school-group.collapsed .disp-chevron {{ transform:rotate(-90deg); }}
.disp-sch-header {{ display:flex; align-items:center; gap:8px; padding:12px 16px; cursor:pointer;
    user-select:none; transition:background .15s; }}
.disp-sch-header:hover {{ background:var(--hover-bg, rgba(0,0,0,.02)); }}
.disp-chevron {{ font-size:11px; color:var(--text-muted); transition:transform .2s; flex-shrink:0; }}
.disp-sch-name {{ font-weight:700; font-size:14px; }}
.disp-sch-chip {{ font-size:10px; font-weight:700; padding:2px 8px; border-radius:99px; }}
.disp-sch-chip.agotado {{ background:var(--red-bg); color:var(--red); }}
.disp-sch-chip.bajo {{ background:var(--orange-bg); color:var(--orange); }}
.disp-sch-chip.ok {{ background:var(--green-bg); color:var(--green); }}
.disp-sch-meta {{ font-size:11px; color:var(--text-muted); margin-left:auto; white-space:nowrap; }}
.disp-sch-bar {{ width:60px; height:6px; background:var(--border-light); border-radius:99px; overflow:hidden; flex-shrink:0; }}
.disp-sch-bar-fill {{ height:100%; border-radius:99px; transition:width .4s ease; }}
.disp-sch-pct {{ font-size:11px; font-weight:700; min-width:32px; text-align:right; }}

.disp-school-body {{ padding:4px 16px 12px; }}

.disp-product-card {{ padding:10px 14px; border-radius:var(--radius-sm); margin-bottom:6px;
    border-left:3px solid transparent; background:var(--bg); transition:box-shadow .15s; }}
.disp-product-card:hover {{ box-shadow:0 1px 4px rgba(0,0,0,.06); }}
.disp-product-card.disp-critico {{ border-left-color:var(--red); }}
.disp-product-card.disp-bajo {{ border-left-color:var(--orange); }}
.disp-product-card.disp-ok {{ border-left-color:var(--green); }}

.disp-prod-header {{ display:flex; align-items:center; gap:8px; margin-bottom:8px; }}
.disp-tipo {{ font-size:10px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:.3px;
    background:var(--border-light); padding:2px 7px; border-radius:4px; }}
.disp-prod-name {{ font-weight:600; font-size:13px; }}
.disp-prod-status {{ font-size:11px; margin-left:auto; font-weight:600; white-space:nowrap; }}
.disp-prod-status.agotado {{ color:var(--red); }}
.disp-prod-status.bajo {{ color:var(--orange); }}
.disp-prod-status.ok {{ color:var(--green); }}

.disp-talla-grid {{ display:flex; flex-wrap:wrap; gap:5px; }}
.disp-talla {{ display:flex; flex-direction:column; align-items:center; justify-content:center;
    min-width:46px; height:42px; border-radius:6px; border:1px solid var(--border);
    padding:0 4px; transition:transform .12s, box-shadow .12s; cursor:default; }}
.disp-talla:hover {{ transform:translateY(-1px); box-shadow:0 2px 6px rgba(0,0,0,.08); }}
.disp-talla-label {{ font-size:10px; font-weight:600; color:var(--text-muted); line-height:1; }}
.disp-talla-stock {{ font-size:14px; font-weight:800; line-height:1.2; }}
.disp-talla-agotado {{ background:var(--red-bg); border-color:color-mix(in srgb, var(--red) 30%, transparent); }}
.disp-talla-agotado .disp-talla-stock {{ color:var(--red); }}
.disp-talla-agotado .disp-talla-label {{ color:var(--red); opacity:.7; }}
.disp-talla-bajo {{ background:var(--orange-bg); border-color:color-mix(in srgb, var(--orange) 30%, transparent); }}
.disp-talla-bajo .disp-talla-stock {{ color:var(--orange); }}
.disp-talla-bajo .disp-talla-label {{ color:var(--orange); opacity:.7; }}
.disp-talla-ok {{ background:var(--green-bg); border-color:color-mix(in srgb, var(--green) 20%, transparent); }}
.disp-talla-ok .disp-talla-stock {{ color:var(--green); }}

@media (max-width: 700px) {{
    .disp-stats {{ flex-wrap:wrap; }}
    .disp-stat {{ min-width:calc(50% - 5px); }}
    .disp-sch-bar, .disp-sch-pct {{ display:none; }}
}}
.num-cell {{ text-align: right; font-variant-numeric: tabular-nums; }}
.val-warn {{ color: var(--orange); font-weight: 700; }}
.val-zero {{ color: var(--red); font-weight: 700; }}
.val-low {{ color: var(--orange); }}
.tallas-cell {{ font-size: 11px; max-width: 220px; }}

/* ============ PRINT ============ */
/* ============ CONTEO ============ */
.conteo-variant-row {{
    display:flex; align-items:center; gap:12px; padding:10px 14px;
    border-bottom:1px solid var(--border-light); flex-wrap:wrap;
}}
.conteo-variant-row:last-child {{ border-bottom:none; }}
.conteo-input {{
    width:80px; padding:6px 8px; border:2px solid var(--border);
    border-radius:var(--radius-xs); text-align:center; font-size:14px;
    font-weight:600; background:var(--card-bg); color:var(--text);
    transition:border-color var(--transition);
}}
.conteo-input::placeholder {{ color:var(--border); opacity:1; }}
.conteo-input:focus {{ border-color:var(--brand); outline:none;
    box-shadow:0 0 0 3px rgba(135,73,44,0.15); }}
.conteo-input.has-value {{ border-color:var(--green); }}
.conteo-input.has-diff {{ border-color:var(--orange); }}
.conteo-diff {{ min-width:50px; text-align:center; font-weight:700; font-size:13px; }}
.conteo-product-card {{ transition:border-left-color var(--transition); border-left:4px solid transparent; }}
.conteo-product-card.card-complete {{ border-left-color:var(--green); }}
.conteo-product-card.card-hasdiff {{ border-left-color:var(--orange); }}
.conteo-status-chip {{
    display:inline-flex; align-items:center; gap:4px;
    padding:2px 8px; border-radius:99px; font-size:11px; font-weight:600;
    background:var(--border-light); color:var(--text-muted);
}}
.conteo-status-chip.done {{ background:var(--green-bg); color:var(--green); }}
.conteo-status-chip.partial {{ background:var(--orange-bg); color:var(--orange); }}
.conteo-adjust-prompt {{
    border-left:4px solid var(--orange); animation:fadeIn 0.3s ease;
}}
.conteo-subtab-panel {{ animation:fadeIn 0.3s ease; }}
.conteo-virtual {{ opacity:0.7; }}
.conteo-virtual .card-header {{ background:var(--border-light); }}
.conteo-sys-stock {{
    font-size:12px; color:var(--text-muted); min-width:80px;
}}

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
    <div class="nav-tab" onclick="showTab('variantes')">Disponibilidad</div>
    <div class="nav-tab" onclick="showTab('conteo')">Conteo</div>
</div>

<div class="page">
    <div id="resumen" class="tab-panel active">{resumen}</div>
    <div id="piezas" class="tab-panel">{pieces}</div>
    <div id="tarifarios" class="tab-panel">{tariffs}</div>

    <div id="variantes" class="tab-panel">{variants}</div>
    <div id="conteo" class="tab-panel">{conteo}</div>
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
    const names = ['resumen','piezas','tarifarios','variantes','conteo'];
    const idx = names.indexOf(id);
    if (idx >= 0) document.querySelectorAll('.nav-tab')[idx].classList.add('active');
}}

/* ---- Piezas: config mode & NA toggle ---- */
let piezasConfigMode = false;

function getPiezasNA() {{
    // Base: defaults from DB (computed by Python)
    const base = window.__defaultNA || {{}};
    // Overrides: manual user toggles stored in localStorage
    try {{
        const overrides = JSON.parse(localStorage.getItem('piezas-na-overrides') || '{{}}');
        const merged = Object.assign({{}}, base);
        for (const key in overrides) {{
            if (overrides[key]) merged[key] = true;
            else delete merged[key];
        }}
        return merged;
    }} catch {{ return base; }}
}}
function savePiezasNA(na) {{
    // Only save the diff vs defaults
    const base = window.__defaultNA || {{}};
    const overrides = {{}};
    for (const key in na) {{
        if (!base[key]) overrides[key] = true;  // user added NA
    }}
    for (const key in base) {{
        if (!na[key]) overrides[key] = false;  // user removed NA
    }}
    localStorage.setItem('piezas-na-overrides', JSON.stringify(overrides));
}}

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
    if (!piezasConfigMode) {{
        togglePiezasConfig();
    }}
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
}}

function recalcResumenCoverage() {{
    /* Resumen ya no tiene coverage-grid individual; noop */
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

// Apply NA config and calc coverage on load
document.addEventListener('DOMContentLoaded', () => {{
    // Clean up old localStorage format (migration)
    localStorage.removeItem('piezas-na');
    const na = getPiezasNA();
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
}});

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

function filterDisponibilidad() {{
    const q = document.getElementById('variantSearch').value.toLowerCase();
    const f = document.getElementById('variantFilter').value;

    document.querySelectorAll('.disp-school-group').forEach(function(group) {{
        const schoolName = (group.dataset.school || '').toLowerCase();
        let anyVisible = false;

        group.querySelectorAll('.disp-product-card').forEach(function(card) {{
            const name = (card.dataset.name || '').toLowerCase();
            const status = card.dataset.status || '';
            let textMatch = schoolName.includes(q) || name.includes(q);
            let filterMatch = true;
            if (f === 'critico') filterMatch = status === 'disp-critico';
            if (f === 'bajo') filterMatch = status === 'disp-bajo';
            if (f === 'ok') filterMatch = status === 'disp-ok';
            const show = textMatch && filterMatch;
            card.style.display = show ? '' : 'none';
            if (show) anyVisible = true;
        }});

        group.style.display = anyVisible ? '' : 'none';
    }});
}}

document.addEventListener('DOMContentLoaded', () => {{
    // Collapse all school/tariff cards by default
    document.querySelectorAll('.school-card, .tariff-card').forEach(c => c.classList.add('collapsed'));
    // Collapse all nivel sections by default
    document.querySelectorAll('.nivel-section').forEach(sec => {{
        sec.classList.add('nivel-collapsed');
    }});
    // Collapse all disponibilidad school groups by default
    document.querySelectorAll('.disp-school-group').forEach(g => g.classList.add('collapsed'));
}});

/* ============ CONTEO DE INVENTARIO ============ */
let _bridge = null;
let _conteoProductos = [];
let _conteoPendientes = [];
let _conteoCurrentFilter = 'todos';
let _conteoLastSavedIds = [];

(function() {{
    if (typeof QWebChannel === 'undefined') {{
        const fb = document.getElementById('conteo-fallback');
        const app = document.getElementById('conteo-app');
        if (fb) fb.style.display = 'block';
        if (app) app.style.display = 'none';
        return;
    }}
    new QWebChannel(qt.webChannelTransport, function(channel) {{
        _bridge = channel.objects.bridge;
    }});
}})();

function _callBridge(method, args, callback) {{
    if (!_bridge) {{ showToast('Bridge no disponible'); return; }}
    _bridge[method](...args, function(resultJson) {{
        const r = JSON.parse(resultJson);
        if (!r.ok) {{ showToast('Error: ' + (r.error || 'desconocido')); return; }}
        callback(r);
    }});
}}

/* ── Sub-tab navigation ── */
function conteoShowSubtab(name) {{
    document.querySelectorAll('.conteo-subtab-panel').forEach(function(p) {{ p.style.display = 'none'; }});
    document.querySelectorAll('#conteo-subtabs button').forEach(function(b) {{ b.classList.remove('active'); }});
    const panel = document.getElementById('conteo-panel-' + name);
    if (panel) panel.style.display = 'block';
    const btn = document.querySelector('#conteo-subtabs button[data-subtab="' + name + '"]');
    if (btn) btn.classList.add('active');
    if (name === 'pendientes') conteoLoadPendientes();
    if (name === 'historial') conteoLoadHistorial();
}}

/* ── Main loader ── */
function conteoLoadEscuela() {{
    const eid = parseInt(document.getElementById('conteo-escuela').value);
    const estado = document.getElementById('conteo-estado');
    const subtabs = document.getElementById('conteo-subtabs');
    if (!eid) {{
        estado.style.display = 'none';
        subtabs.style.display = 'none';
        document.querySelectorAll('.conteo-subtab-panel').forEach(function(p) {{ p.style.display = 'none'; }});
        document.getElementById('conteo-guardar-btn').disabled = true;
        return;
    }}
    // Load estado
    _callBridge('getEstadoConteo', [eid], function(r) {{
        const info = document.getElementById('conteo-estado-info');
        const pct = r.pct_vigente;
        const color = pct >= 80 ? 'var(--green)' : pct >= 40 ? 'var(--orange)' : 'var(--red)';
        const semaforo = pct >= 80 ? '🟢' : pct >= 40 ? '🟡' : '🔴';
        info.innerHTML = semaforo + ' <b>' + r.escuela_nombre + '</b> — ' +
            '<span style="color:' + color + ';font-weight:700">' + pct + '% vigente</span> · ' +
            r.contadas_vigentes + '/' + r.total_variantes + ' contadas · ' +
            '<span style="color:var(--orange)">' + r.pendientes_conteo + ' pendientes</span>' +
            (r.ultimo_conteo ? ' · Ultimo: ' + new Date(r.ultimo_conteo).toLocaleDateString() : '');
        document.getElementById('conteo-vigencia').value = r.dias_vigencia;
        estado.style.display = 'block';
    }});
    _callBridge('getConfigConteo', [eid], function(r) {{
        document.getElementById('conteo-vigencia').value = r.dias_vigencia;
    }});
    // Load grouped variants
    _callBridge('getVariantesAgrupadas', [eid], function(r) {{
        _conteoProductos = r.data;
        conteoRenderProducts();
        subtabs.style.display = 'flex';
        conteoShowSubtab('contar');
        conteoUpdateProgress();
        document.getElementById('conteo-guardar-btn').disabled = false;
    }});
    // Update pendientes badge
    _callBridge('getConteosPendientes', [eid], function(r) {{
        const badge = document.getElementById('conteo-pendientes-badge');
        if (r.data.length > 0) {{
            badge.textContent = r.data.length;
            badge.style.display = 'inline';
        }} else {{
            badge.style.display = 'none';
        }}
    }});
}}

/* ── Render product cards ── */
function conteoRenderProducts() {{
    const container = document.getElementById('conteo-products-container');
    container.innerHTML = '';
    if (!_conteoProductos.length) {{
        container.innerHTML = '<div class="section-card" style="text-align:center;padding:30px;color:var(--text-muted)">No hay variantes para esta escuela</div>';
        return;
    }}
    _conteoProductos.forEach(function(grupo, gi) {{
        const card = document.createElement('div');
        card.className = 'school-card conteo-product-card';
        if (grupo.virtual) card.classList.add('conteo-virtual');
        card.dataset.product = grupo.producto_nombre;
        card.dataset.groupIdx = gi;
        card.dataset.virtual = grupo.virtual ? '1' : '0';

        const totalV = grupo.variantes.length;
        const isVirtual = !!grupo.virtual;

        // Header
        const header = document.createElement('div');
        header.className = 'card-header';
        header.onclick = function() {{ card.classList.toggle('collapsed'); }};

        const tipoTag = '<span class="tipo-tag">' + grupo.tipo_pieza + '</span>';
        const virtualTag = isVirtual ? ' <span class="meta-chip" style="background:var(--purple);color:#fff;font-size:10px">Virtual</span>' : '';

        header.innerHTML =
            '<div class="card-title-row" style="gap:8px">' +
                tipoTag +
                '<span class="card-title">' + grupo.producto_nombre + '</span>' +
                virtualTag +
            '</div>' +
            '<div style="display:flex;align-items:center;gap:8px">' +
                '<span class="meta-chip">' + totalV + (totalV === 1 ? ' talla' : ' tallas') + '</span>' +
                (isVirtual ? '' : '<span class="conteo-status-chip" data-group="' + gi + '">0/' + totalV + '</span>') +
                '<span class="toggle-arrow">&#9662;</span>' +
            '</div>';
        card.appendChild(header);

        // Body
        const body = document.createElement('div');
        body.className = 'card-body';
        body.style.padding = '4px 14px 10px';

        if (isVirtual) {{
            // Virtual product info message
            body.innerHTML = '<div style="padding:10px 0;color:var(--text-muted);font-size:13px;display:flex;align-items:center;gap:8px">' +
                '<span style="font-size:16px">📦</span> Producto virtual — se arma con componentes individuales. ' +
                'El stock se cuenta en cada componente por separado.</div>';
        }} else {{
            // Normal variant rows
            grupo.variantes.forEach(function(v) {{
                const row = document.createElement('div');
                row.className = 'conteo-variant-row';
                row.dataset.sku = v.sku;

                const statusColor = v.requiere_conteo ? (v.ultimo_conteo_at ? 'var(--orange)' : 'var(--red)') : 'var(--green)';
                const statusDot = '<span style="width:8px;height:8px;border-radius:50%;background:' + statusColor + ';flex-shrink:0" title="' +
                    (v.requiere_conteo ? (v.ultimo_conteo_at ? 'Vencido' : 'Nunca contado') : 'Vigente') + '"></span>';

                var ubicChips = '';
                if (v.stock_piso > 0) ubicChips += '<span class="meta-chip" style="font-size:10px;background:var(--orange-bg,#fff3e0);color:var(--orange,#e65100);padding:1px 6px">Piso: ' + v.stock_piso + '</span>';
                if (v.stock_bodega > 0) ubicChips += '<span class="meta-chip" style="font-size:10px;background:var(--blue-bg,#e3f2fd);color:var(--blue,#1565c0);padding:1px 6px">Almacén: ' + v.stock_bodega + '</span>';

                row.innerHTML =
                    statusDot +
                    '<span style="font-family:monospace;font-size:11px;color:var(--text-muted);min-width:55px">' + v.sku + '</span>' +
                    '<span style="font-weight:600;min-width:50px">' + v.talla + '</span>' +
                    '<span class="meta-chip" style="font-size:11px">' + v.color + '</span>' +
                    ubicChips +
                    '<span class="conteo-sys-stock">Tienda: ' + v.stock_tienda + '</span>' +
                    '<input type="number" class="conteo-input" data-varid="' + v.variante_id + '" data-stock="' + v.stock_tienda + '" data-group="' + gi + '" ' +
                        'placeholder="' + v.stock_tienda + '" min="0" oninput="conteoOnInput(this)">' +
                    '<span class="conteo-diff" data-varid="' + v.variante_id + '">—</span>';
                body.appendChild(row);
            }});
        }}

        card.appendChild(body);
        // Virtual cards start collapsed
        if (isVirtual) card.classList.add('collapsed');
        container.appendChild(card);
    }});
    document.getElementById('conteo-adjust-prompt').style.display = 'none';
}}

/* ── Input handler ── */
function conteoOnInput(input) {{
    const stock = parseInt(input.dataset.stock);
    const varid = input.dataset.varid;
    const diffEl = document.querySelector('.conteo-diff[data-varid="' + varid + '"]');
    const val = input.value.trim();

    if (val === '') {{
        diffEl.textContent = '—';
        diffEl.style.color = 'var(--text-muted)';
        input.className = 'conteo-input';
    }} else {{
        const fisico = parseInt(val) || 0;
        const diff = fisico - stock;
        if (diff === 0) {{
            diffEl.textContent = '0';
            diffEl.style.color = 'var(--text-muted)';
            input.className = 'conteo-input has-value';
        }} else {{
            diffEl.textContent = diff > 0 ? '+' + diff : '' + diff;
            diffEl.style.color = diff > 0 ? 'var(--green)' : 'var(--red)';
            input.className = 'conteo-input has-diff';
        }}
    }}
    // Update card status
    conteoUpdateCardStatus(parseInt(input.dataset.group));
    conteoUpdateProgress();
    // Enable save if any input has value
    const anyFilled = document.querySelector('.conteo-input[data-varid]');
    let hasFilled = false;
    document.querySelectorAll('.conteo-input[data-varid]').forEach(function(inp) {{
        if (inp.value.trim() !== '') hasFilled = true;
    }});
    document.getElementById('conteo-guardar-btn').disabled = !hasFilled;
}}

function conteoUpdateCardStatus(groupIdx) {{
    const inputs = document.querySelectorAll('.conteo-input[data-group="' + groupIdx + '"]');
    let filled = 0;
    let hasDiff = false;
    inputs.forEach(function(inp) {{
        if (inp.value.trim() !== '') {{
            filled++;
            const stock = parseInt(inp.dataset.stock);
            const fisico = parseInt(inp.value) || 0;
            if (fisico !== stock) hasDiff = true;
        }}
    }});
    const total = inputs.length;
    const chip = document.querySelector('.conteo-status-chip[data-group="' + groupIdx + '"]');
    chip.textContent = filled + '/' + total;
    chip.className = 'conteo-status-chip' + (filled === total ? ' done' : filled > 0 ? ' partial' : '');

    const card = document.querySelector('.conteo-product-card[data-group-idx="' + groupIdx + '"]');
    card.classList.remove('card-complete', 'card-hasdiff');
    if (filled === total && !hasDiff) card.classList.add('card-complete');
    else if (hasDiff) card.classList.add('card-hasdiff');
}}

/* ── Progress bar ── */
function conteoUpdateProgress() {{
    let totalProducts = 0;
    let countedProducts = 0;
    _conteoProductos.forEach(function(g, gi) {{
        if (g.virtual) return; // Skip virtual products
        totalProducts++;
        const inputs = document.querySelectorAll('.conteo-input[data-group="' + gi + '"]');
        let allFilled = true;
        inputs.forEach(function(inp) {{
            if (inp.value.trim() === '') allFilled = false;
        }});
        if (allFilled && inputs.length > 0) countedProducts++;
    }});
    const pct = totalProducts > 0 ? Math.round(countedProducts / totalProducts * 100) : 0;
    document.getElementById('conteo-progress-text').textContent = countedProducts + ' de ' + totalProducts + ' productos contados';
    document.getElementById('conteo-progress-pct').textContent = pct + '%';
    document.getElementById('conteo-progress-fill').style.width = pct + '%';
}}

/* ── Search & filter ── */
function conteoFilterProducts() {{
    const search = (document.getElementById('conteo-search').value || '').toLowerCase();
    document.querySelectorAll('.conteo-product-card').forEach(function(card) {{
        const name = (card.dataset.product || '').toLowerCase();
        const skus = Array.from(card.querySelectorAll('[data-sku]')).map(function(r) {{ return (r.dataset.sku || '').toLowerCase(); }});
        const matchSearch = !search || name.indexOf(search) >= 0 || skus.some(function(s) {{ return s.indexOf(search) >= 0; }});

        let matchFilter = true;
        if (_conteoCurrentFilter === 'sincontar') {{
            const inputs = card.querySelectorAll('.conteo-input');
            let allFilled = true;
            inputs.forEach(function(inp) {{ if (inp.value.trim() === '') allFilled = false; }});
            matchFilter = !allFilled;
        }} else if (_conteoCurrentFilter === 'diferencia') {{
            const inputs = card.querySelectorAll('.conteo-input');
            let anyDiff = false;
            inputs.forEach(function(inp) {{
                if (inp.value.trim() !== '') {{
                    const fisico = parseInt(inp.value) || 0;
                    const stock = parseInt(inp.dataset.stock);
                    if (fisico !== stock) anyDiff = true;
                }}
            }});
            matchFilter = anyDiff;
        }}
        card.style.display = (matchSearch && matchFilter) ? '' : 'none';
    }});
}}

function conteoSetFilter(filter, btn) {{
    _conteoCurrentFilter = filter;
    document.querySelectorAll('#conteo-panel-contar .filter-bar button[data-filter]').forEach(function(b) {{ b.classList.remove('active'); }});
    if (btn) btn.classList.add('active');
    conteoFilterProducts();
}}

/* ── Save ── */
function conteoGuardar() {{
    const contadoPor = document.getElementById('conteo-por').value.trim();
    if (!contadoPor) {{ showToast('Ingresa quien realiza el conteo'); return; }}
    const inputs = document.querySelectorAll('.conteo-input[data-varid]');
    const conteos = [];
    inputs.forEach(function(inp) {{
        if (inp.value.trim() !== '') {{
            conteos.push({{ variante_id: parseInt(inp.dataset.varid), stock_fisico: parseInt(inp.value) || 0 }});
        }}
    }});
    if (!conteos.length) {{ showToast('No hay variantes contadas'); return; }}
    const payload = JSON.stringify({{ contado_por: contadoPor, conteos: conteos }});
    document.getElementById('conteo-guardar-btn').disabled = true;
    _callBridge('guardarConteo', [payload], function(r) {{
        showToast('Conteo guardado: ' + r.total + ' variantes (' + r.con_diferencia + ' con diferencia)');
        if (r.con_diferencia > 0) {{
            // Show inline adjust prompt
            const prompt = document.getElementById('conteo-adjust-prompt');
            document.getElementById('conteo-adjust-msg').innerHTML =
                '<b>' + r.con_diferencia + '</b> variante(s) con diferencia de stock.';
            prompt.style.display = 'block';
            prompt.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
        }} else {{
            conteoLoadEscuela();
        }}
        // Update pendientes badge
        const eid = parseInt(document.getElementById('conteo-escuela').value);
        _callBridge('getConteosPendientes', [eid], function(r2) {{
            const badge = document.getElementById('conteo-pendientes-badge');
            if (r2.data.length > 0) {{
                badge.textContent = r2.data.length;
                badge.style.display = 'inline';
            }} else {{
                badge.style.display = 'none';
            }}
        }});
    }});
}}

function conteoApplyAdjustments() {{
    const eid = parseInt(document.getElementById('conteo-escuela').value);
    _callBridge('getConteosPendientes', [eid], function(r) {{
        if (!r.data.length) {{ showToast('No hay ajustes pendientes'); conteoLoadEscuela(); return; }}
        const ids = r.data.map(function(c) {{ return c.id; }});
        _callBridge('confirmarAjuste', [JSON.stringify(ids)], function(r2) {{
            showToast('Stock ajustado: ' + r2.ajustados + ' variante(s)');
            conteoLoadEscuela();
        }});
    }});
}}

function conteoDismissPrompt() {{
    document.getElementById('conteo-adjust-prompt').style.display = 'none';
    conteoShowSubtab('pendientes');
}}

/* ── Config ── */
function conteoGuardarConfig() {{
    const eid = parseInt(document.getElementById('conteo-escuela').value);
    const dias = parseInt(document.getElementById('conteo-vigencia').value);
    if (!eid || !dias || dias < 1) return;
    _callBridge('setConfigConteo', [eid, dias], function() {{
        showToast('Vigencia actualizada a ' + dias + ' dias');
        conteoLoadEscuela();
    }});
}}

/* ── Pendientes ── */
function conteoLoadPendientes() {{
    const eid = parseInt(document.getElementById('conteo-escuela').value) || 0;
    _callBridge('getConteosPendientes', [eid], function(r) {{
        _conteoPendientes = r.data;
        const container = document.getElementById('conteo-pendientes-container');
        const empty = document.getElementById('conteo-pendientes-empty');
        const countEl = document.getElementById('conteo-pendientes-count');
        container.innerHTML = '';

        if (!r.data.length) {{
            container.style.display = 'none';
            empty.style.display = 'block';
            countEl.textContent = '';
            document.getElementById('conteo-ajustar-btn').disabled = true;
        }} else {{
            container.style.display = 'block';
            empty.style.display = 'none';
            countEl.textContent = r.data.length + ' pendiente' + (r.data.length > 1 ? 's' : '');

            r.data.forEach(function(c) {{
                const diffColor = c.diferencia > 0 ? 'var(--green)' : 'var(--red)';
                const diffSign = c.diferencia > 0 ? '+' : '';
                const fecha = c.contado_at ? _conteoFormatFecha(c.contado_at) : '—';

                const card = document.createElement('div');
                card.style.cssText = 'display:flex;align-items:center;gap:12px;padding:10px 14px;border:1px solid var(--border);border-radius:8px;margin-bottom:8px;background:var(--bg-card,#fff);transition:background .15s';
                card.onmouseenter = function(){{ this.style.background='var(--bg-hover,#fafafa)'; }};
                card.onmouseleave = function(){{ this.style.background='var(--bg-card,#fff)'; }};

                card.innerHTML =
                    '<input type="checkbox" class="conteo-check" value="' + c.id + '" onchange="conteoUpdateCheckInfo()" style="width:16px;height:16px;cursor:pointer;flex-shrink:0">' +
                    '<div style="flex:1;min-width:0">' +
                        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">' +
                            '<span style="font-weight:600">' + c.producto + '</span>' +
                            '<span style="font-family:monospace;font-size:11px;color:var(--text-muted)">' + c.sku + '</span>' +
                        '</div>' +
                        '<div style="display:flex;align-items:center;gap:12px;margin-top:4px;font-size:13px;color:var(--text-muted)">' +
                            '<span>Sistema: <b style="color:var(--text)">' + c.stock_sistema + '</b></span>' +
                            '<span>Físico: <b style="color:var(--text)">' + c.stock_fisico + '</b></span>' +
                            '<span>👤 ' + c.contado_por + '</span>' +
                            '<span>📅 ' + fecha + '</span>' +
                        '</div>' +
                    '</div>' +
                    '<div style="text-align:center;flex-shrink:0;min-width:50px">' +
                        '<div style="font-size:20px;font-weight:700;color:' + diffColor + '">' + diffSign + c.diferencia + '</div>' +
                        '<div style="font-size:10px;color:var(--text-muted)">' + (c.diferencia > 0 ? 'sobran' : 'faltan') + '</div>' +
                    '</div>';
                container.appendChild(card);
            }});
            document.getElementById('conteo-ajustar-btn').disabled = false;
        }}
    }});
}}

function _conteoFormatFecha(iso) {{
    try {{
        const d = new Date(iso);
        const now = new Date();
        const diffMs = now - d;
        const diffDays = Math.floor(diffMs / 86400000);
        if (diffDays === 0) return 'Hoy ' + d.toLocaleTimeString([], {{hour:'2-digit',minute:'2-digit'}});
        if (diffDays === 1) return 'Ayer';
        if (diffDays < 7) return 'Hace ' + diffDays + 'd';
        return d.toLocaleDateString();
    }} catch(e) {{ return iso; }}
}}

function conteoToggleAll(master) {{
    document.querySelectorAll('.conteo-check').forEach(function(cb) {{ cb.checked = master.checked; }});
    conteoUpdateCheckInfo();
}}

function conteoUpdateCheckInfo() {{
    const checked = document.querySelectorAll('.conteo-check:checked').length;
    document.getElementById('conteo-ajustar-btn').disabled = checked === 0;
    document.getElementById('conteo-ajustar-btn').textContent = checked > 0 ? 'Confirmar ' + checked + ' ajuste' + (checked > 1 ? 's' : '') : 'Confirmar seleccionados';
}}

function conteoConfirmarAjustes() {{
    const checks = document.querySelectorAll('.conteo-check:checked');
    if (!checks.length) {{ showToast('Selecciona al menos un conteo'); return; }}
    const ids = Array.from(checks).map(function(cb) {{ return parseInt(cb.value); }});
    _callBridge('confirmarAjuste', [JSON.stringify(ids)], function(r) {{
        showToast('Ajustados: ' + r.ajustados + (r.omitidos > 0 ? ', Omitidos: ' + r.omitidos : ''));
        conteoLoadEscuela();
    }});
}}

/* ── Historial ── */
function conteoLoadHistorial() {{
    const eid = parseInt(document.getElementById('conteo-escuela').value) || 0;
    if (!eid) return;
    _callBridge('getHistorialConteos', [eid, 50], function(r) {{
        const container = document.getElementById('conteo-historial-container');
        const empty = document.getElementById('conteo-historial-empty');
        const countEl = document.getElementById('conteo-historial-count');
        container.innerHTML = '';

        if (!r.data.length) {{
            container.style.display = 'none';
            empty.style.display = 'block';
            countEl.textContent = '';
        }} else {{
            container.style.display = 'block';
            empty.style.display = 'none';
            countEl.textContent = r.data.length + ' registro' + (r.data.length > 1 ? 's' : '');

            r.data.forEach(function(c) {{
                const diffColor = c.diferencia === 0 ? 'var(--text-muted)' : (c.diferencia > 0 ? 'var(--green)' : 'var(--red)');
                const diffSign = c.diferencia > 0 ? '+' : '';
                const diffText = c.diferencia === 0 ? '0' : diffSign + c.diferencia;
                const fecha = c.contado_at ? _conteoFormatFecha(c.contado_at) : '—';
                const statusIcon = c.ajustado ? '✅' : '⏳';
                const statusText = c.ajustado ? 'Ajustado' : 'Pendiente';
                const borderColor = c.diferencia === 0 ? 'var(--border)' : (c.ajustado ? 'var(--green)' : 'var(--orange)');

                const card = document.createElement('div');
                card.style.cssText = 'display:flex;align-items:center;gap:12px;padding:10px 14px;border:1px solid var(--border);border-left:3px solid ' + borderColor + ';border-radius:8px;margin-bottom:6px;background:var(--bg-card,#fff);font-size:13px';

                card.innerHTML =
                    '<div style="flex:1;min-width:0">' +
                        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">' +
                            '<span style="font-weight:600">' + c.producto + '</span>' +
                            '<span style="font-family:monospace;font-size:11px;color:var(--text-muted)">' + c.sku + '</span>' +
                            '<span style="font-size:11px">' + statusIcon + ' ' + statusText + '</span>' +
                        '</div>' +
                        '<div style="display:flex;align-items:center;gap:12px;margin-top:3px;color:var(--text-muted)">' +
                            '<span>Sistema: <b style="color:var(--text)">' + c.stock_sistema + '</b></span>' +
                            '<span>Físico: <b style="color:var(--text)">' + c.stock_fisico + '</b></span>' +
                            '<span>Dif: <b style="color:' + diffColor + '">' + diffText + '</b></span>' +
                            '<span>👤 ' + c.contado_por + '</span>' +
                            '<span>📅 ' + fecha + '</span>' +
                            (c.notas ? '<span>📝 ' + c.notas + '</span>' : '') +
                        '</div>' +
                    '</div>';
                container.appendChild(card);
            }});
        }}
    }});
}}
</script>

<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
if (typeof QWebChannel !== 'undefined' && typeof qt !== 'undefined') {{
    new QWebChannel(qt.webChannelTransport, function(channel) {{
        _bridge = channel.objects.bridge;
        const fb = document.getElementById('conteo-fallback');
        const app = document.getElementById('conteo-app');
        if (fb) fb.style.display = 'none';
        if (app) app.style.display = 'block';
    }});
}}
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
    variants = build_variants(catalog_rows, catalog_cols, multi_level_ids)
    conteo = build_conteo(school_levels)

    html = generate_html(resumen, pieces, tariffs, variants, conteo)

    out_path = Path(__file__).resolve().parent.parent / "panel_uniformes.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Panel generado: {out_path}")
    print(f"  Abre: file://{out_path}")


if __name__ == "__main__":
    main()
