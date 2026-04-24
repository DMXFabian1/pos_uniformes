#!/usr/bin/env python3
"""Genera tarifarios en HTML/CSS — tamaño carta, diseño limpio."""

from pathlib import Path

OUT = Path(__file__).parent / "tarifarios_html"
OUT.mkdir(exist_ok=True)

# ── CSS base ─────────────────────────────────────────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --navy:       #1B3557;
  --navy-mid:   #2C4E80;
  --blue-light: #EBF2FF;
  --accent:     #C96030;
  --accent-lt:  #FEF3EC;
  --red:        #C92020;
  --red-lt:     #FEF0F0;
  --border:     #DDE4EF;
  --row-alt:    #F5F8FF;
  --text:       #16202E;
  --muted:      #64748B;
  --surface:    #FFFFFF;
  --bg:         #F3F5FA;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  line-height: 1.4;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

/* ── Página ───────────────────────────────────────────────────────────────── */
.page {
  width: 11in;
  min-height: 8.5in;
  background: var(--surface);
  margin: 0 auto 32px;
  padding: 0.42in 0.52in 0.38in;
  box-shadow: 0 2px 20px rgba(27,53,87,0.10);
  display: flex;
  flex-direction: column;
  gap: 0;
}

@page { size: letter landscape; margin: 0; }

@media print {
  body { background: white; }
  .page {
    margin: 0;
    box-shadow: none;
    page-break-after: always;
  }
  .page:last-child { page-break-after: avoid; }
}

/* ── Header ───────────────────────────────────────────────────────────────── */
.page-header {
  background: linear-gradient(120deg, var(--navy) 0%, var(--navy-mid) 100%);
  border-radius: 10px;
  padding: 13px 22px;
  margin-bottom: 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.page-header::before {
  content: '';
  position: absolute;
  width: 180px; height: 180px;
  border-radius: 50%;
  background: rgba(255,255,255,0.04);
  top: -60px; right: -40px;
}

.page-header::after {
  content: '';
  position: absolute;
  width: 90px; height: 90px;
  border-radius: 50%;
  background: rgba(255,255,255,0.06);
  bottom: -30px; right: 120px;
}

.header-left { z-index: 1; }

.header-category {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: rgba(255,255,255,0.55);
  margin-bottom: 3px;
}

.header-title {
  font-size: 26px;
  font-weight: 800;
  color: white;
  letter-spacing: -0.5px;
}

.header-right {
  z-index: 1;
  text-align: right;
}

.header-date {
  font-size: 10px;
  color: rgba(255,255,255,0.45);
}

/* ── Grids ────────────────────────────────────────────────────────────────── */
.grid { display: grid; gap: 10px; margin-bottom: 10px; }
.cols-2 { grid-template-columns: repeat(2, 1fr); }
.cols-3 { grid-template-columns: repeat(3, 1fr); }
.cols-4 { grid-template-columns: repeat(4, 1fr); }
.cols-1 { grid-template-columns: 1fr; }

/* ── Table block ──────────────────────────────────────────────────────────── */
.block { break-inside: avoid; }

.block-title {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.3px;
  color: var(--navy);
  text-transform: uppercase;
  padding: 5px 10px 5px 11px;
  background: var(--blue-light);
  border-left: 3px solid var(--navy-mid);
  border-radius: 0 5px 0 0;
  margin-bottom: 0;
}

.block-title.exc {
  color: var(--red);
  background: var(--red-lt);
  border-left-color: var(--red);
}

/* ── Tables ───────────────────────────────────────────────────────────────── */
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
  border: 1px solid var(--border);
  border-top: none;
}

thead th {
  background: #F0F4FB;
  color: #334155;
  font-weight: 600;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  padding: 4px 9px;
  border-bottom: 1.5px solid var(--border);
  text-align: left;
  white-space: nowrap;
}

thead th:not(:first-child) { text-align: right; }

tbody td {
  padding: 4px 9px;
  border-bottom: 1px solid #EDF2F8;
  color: var(--text);
}

tbody td:not(:first-child) {
  text-align: right;
  font-weight: 700;
  font-size: 13px;
  color: var(--navy);
}

tbody tr:nth-child(even) td { background: var(--row-alt); }
tbody tr:last-child td { border-bottom: none; }

/* Exception tables */
.exc-table thead th {
  background: #FEF0F0;
  color: #7F1D1D;
  border-bottom-color: #FECACA;
}
.exc-table tbody td:not(:first-child) { color: var(--red); }
.exc-table tbody tr:nth-child(even) td { background: #FFF7F7; }
.exc-table { border-color: #FECACA; }

/* ── Section divider ──────────────────────────────────────────────────────── */
.divider {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 11px 0 8px;
  font-size: 9.5px;
  font-weight: 700;
  color: #94A3B8;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #E2E8F0;
}

/* ── Notes ────────────────────────────────────────────────────────────────── */
.notes {
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid #EDF2F8;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.notes p {
  font-size: 10px;
  color: var(--muted);
  font-style: italic;
  display: flex;
  gap: 5px;
}

.notes p::before {
  content: '–';
  color: #CBD5E1;
  flex-shrink: 0;
}
"""

# ── Helper para construir HTML de bloque ─────────────────────────────────────
def block(title: str, headers: list, rows: list, exc=False) -> str:
    cls = "exc" if exc else ""
    tbl_cls = "exc-table" if exc else ""
    title_cls = "exc" if exc else ""

    ths = "".join(f"<th>{h}</th>" for h in headers)
    trs = ""
    for row in rows:
        tds = "".join(f"<td>{v}</td>" for v in row)
        trs += f"<tr>{tds}</tr>"

    return f"""
<div class="block">
  <div class="block-title {title_cls}">{title}</div>
  <table class="{tbl_cls}">
    <thead><tr>{ths}</tr></thead>
    <tbody>{trs}</tbody>
  </table>
</div>"""


def grid(cols: int, *blocks: str) -> str:
    inner = "\n".join(blocks)
    return f'<div class="grid cols-{cols}">{inner}</div>'


def divider(label: str) -> str:
    return f'<div class="divider">{label}</div>'


def notes(*lines: str) -> str:
    return ""


# ── Estructura de cada página ─────────────────────────────────────────────────
def page(category: str, title: str, rule: str, body: str) -> str:
    return f"""
<div class="page">
  <div class="page-header">
    <div class="header-left">
      <div class="header-category">Tarifario Rápido · {category}</div>
      <div class="header-title">{title}</div>
    </div>
    <div class="header-right">
      <div class="header-date">Actualizado: Abril 2026</div>
    </div>
  </div>
  {body}
</div>"""


# ══════════════════════════════════════════════════════════════════════════════
#  CONTENIDO
# ══════════════════════════════════════════════════════════════════════════════

RULE = "precio = MAX(actual, objetivo)"

def build_playeras():
    body = grid(4,
        block("Preescolar", ["Tallas", "Precio"],
              [["2, 4, 6, 8, 10","$175"],["12, 14, 16","$199"],["CH, MD, GD, EXG","$219"]]),
        block("Primaria", ["Tallas", "Precio"],
              [["4, 6, 8, 10","$199"],["12, 14, 16","$209"],["CH, MD, GD, EXG","$219"]]),
        block("Secundaria", ["Tallas", "Precio"],
              [["12, 14, 16","$229"],["CH, MD, GD, EXG","$239"]]),
        block("Bachillerato", ["Tallas", "Precio"],
              [["12, 14, 16","$229"],["CH, MD, GD, EXG","$239"]]),
    ) + notes("Si una playera ya tiene precio mayor marcado, se respeta.")
    return page("Ropa Deportiva", "Playeras Deportivas", RULE, body)


def build_sueteres():
    body = grid(3,
        block("Básico", ["Tallas", "Precio"],
              [["4, 6, 8","$289"],["10, 12, 14, 16","$299"],["30, 32, 34","$309"],
               ["36, 38, 40, 42","$315"],["44, 46","$325"]]),
        block("Oficial Preescolar", ["Tallas", "Precio"],
              [["4, 6, 8, 10","$290"]]),
        block("Oficial Primaria", ["Tallas", "Precio"],
              [["4, 6, 8, 10","$290"],["12, 14, 16","$315"],["30 – 42","$325"]]),
        block("Oficial Secundaria", ["Tallas", "Precio"],
              [["12, 14, 16","$325"],["30 – 44","$345"]]),
        block("Oficial Bachillerato", ["Tallas", "Precio"],
              [["14, 16","$325"],["32, 34","$335"],["36, 38","$345"],["40, 42, 44","$355"]]),
    ) + divider("Excepciones activas") + grid(2,
        block("Primaria", ["Escuela", "Tallas", "Precio"],
              [["Benito Juárez","40, 42","$335"],["Colegio Motolinea","40","$335"],
               ["Francisco Villa","40","$335"],["Ignacio Allende","40","$335"],
               ["Miguel Hidalgo","40, 42","$335"]], exc=True),
        block("Bachillerato", ["Escuela", "Tallas", "Precio"],
              [["UVEG","14, 16, 32–42","$355"]], exc=True),
    ) + notes(
        "Suéter Oferta Ad hoc Talla Uni se maneja aparte a $199.",
        "Si una escuela aparece en excepciones, respetar ese precio.",
    )
    return page("Suéteres", "Suéteres", RULE, body)


def build_chamarras():
    body = grid(3,
        block("Deportiva · Con Escudo", ["Nivel", "Tallas", "Precio"],
              [["Preescolar","4, 6, 8","$315"],["Primaria","4–16, CH, MD, GD","$335"],
               ["Secundaria","12–16, CH–EXG","$385"],["Bachillerato","12–16, CH–EXG","$385"]]),
        block("Básica Liso", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$175"],["10, 12","$195"],["14, 16","$215"],
               ["28, CH, MD, GD, EXG","$235"]]),
        block("Básica Punto", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$275"],["10, 12, 14, 16","$295"],["28, CH","$385"],
               ["MD","$395"],["GD","$405"],["EXG","$415"]]),
    ) + notes(
        "No heredar precios de Chamarra Básica a Chamarra Deportiva.",
        "Si una prenda ya tiene precio mayor marcado, se respeta.",
    )
    return page("Chamarras", "Chamarras", RULE, body)


def build_chalecos():
    body = grid(4,
        block("Básico · sin escuela", ["Tallas", "Precio"],
              [["4, 6, 8","$229"],["10, 12, 14, 16","$239"],["28, 30, 32, 34","$259"],
               ["36 – 46","$269"]]),
        block("Oficial por escuela (estándar)", ["Tallas", "Precio"],
              [["4, 6, 8","$240"],["10, 12","$250"],["14, 16","$260"],
               ["32, 34","$290"],["36, 38, 40","$300"]]),
        block("Práxedis Guerrero · Telesec. 512", ["Tallas", "Precio"],
              [["12, 14, 16","$245"],["30, 32, 34","$265"],["36 – 44","$275"]]),
        block("SABES (Bachillerato)", ["Tallas", "Precio"],
              [["14, 16","$285"],["32 – 42","$285"],["44","$295"]]),
    ) + divider("Notas por escuela") + grid(2,
        block("Colegio Motolinea", ["Tallas", "Precio"],
              [["4, 6, 8","$240"],["10, 12","$250"],["14, 16","$260"],
               ["CH, MD, GD, EXG","$270"]]),
        block("Excepciones activas", ["Escuela", "Tallas", "Precio"],
              [["Huizache","6, 8","$240"],["Huizache","10, 12","$245"],
               ["Huizache","14, 16","$250"],["Huizache","34, 36","$270"]], exc=True),
    )
    return page("Chalecos", "Chalecos", RULE, body)


def build_camisas():
    body = grid(4,
        block("Manga Corta Blanca", ["Tallas", "Precio"],
              [["4, 6, 8","$89"],["10, 12, 14, 16","$99"],["28, 30","$115"],
               ["32, 34","$135"],["36, 38","$145"],["40, 42","$165"]]),
        block("Prowear Manga Corta", ["Tallas", "Precio"],
              [["4, 6, 8","$125"],["10, 12","$145"],["14, 16","$155"],
               ["28 – 38","$165"],["40, 42","$185"]]),
        block("Manga Larga H Blanca", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$199"],["10 – 18","$219"],["32, 34","$239"],
               ["36, 38","$249"],["40, 42, 44, CH","$259"],
               ["MD","$269"],["GD","$279"],["EXG","$289"]]),
        block("Manga Larga M Blanca", ["Tallas", "Precio"],
              [["30, CH","$269"],["MD, GD","$289"],["EXG","$309"]]),
        block("Oficial Preescolar", ["Tallas", "Precio"],
              [["Línea completa","$139"]]),
        block("Oficial Primaria", ["Tallas", "Precio"],
              [["4, 6, 8, 10","$215"],["12, 14, 16","$225"],["32 – 38","$245"]]),
        block("Oficial Secundaria", ["Tallas", "Precio"],
              [["Línea completa","$265"]]),
        block("Oficial Bachillerato", ["Tallas", "Precio"],
              [["Línea completa","$265"]]),
    ) + divider("Excepciones activas") + grid(1,
        block("Camisas oficiales por escuela", ["Escuela", "Línea", "Precio"],
              [["Francisco Villa","Oficial Primaria","$215 / $225 / $245"],
               ["Bicentenario","Oficial Secundaria","$265"],
               ["CBTIS 148","Oficial Bachillerato","$265"],
               ["Conalep","Oficial Bachillerato","$265"]], exc=True),
    ) + notes("Si aparece Camisa Manga Larga Blanca a $265 sin nivel, conservar precio.")
    return page("Camisas", "Camisas", RULE, body)


def build_pants_2pz():
    body = divider("Liso · Punto · Algodón (genérico)") + grid(3,
        block("Liso · todos los colores", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$250"],["10, 12, 14, 16","$265"],
               ["28, CH","$315"],["MD","$325"],["GD","$335"],["EXG","$345"]]),
        block("Punto · todos los colores", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$475"],["10, 12, 14, 16","$495"],
               ["28, CH","$525"],["MD","$535"],["GD","$545"],["EXG","$555"]]),
        block("Algodón Azul Marino", ["Tallas", "Precio"],
              [["4, 6, 8","$260"],["10, 12","$265"],["14, 16","$275"]]),
    ) + divider("Deportivo por nivel") + grid(4,
        block("Preescolar", ["Tallas", "2 pzas", "3 pzas"],
              [["2, 4, 6, 8, 10","$445","$545"]]),
        block("Primaria", ["Tallas", "2 pzas", "3 pzas"],
              [["4, 6, 8, 10, 12","$485","$585"],["14, 16","$495","$595"],
               ["CH, MD, GD","$585","$685"]]),
        block("Secundaria", ["Tallas", "2 pzas", "3 pzas"],
              [["10, 12","$595","$695"],["14, 16","$605","$705"],
               ["CH, MD, GD, EXG","$615","$715"]]),
        block("Bachillerato", ["Tallas", "2 pzas", "3 pzas"],
              [["16","$615","$715"],["CH, MD, GD, EXG","$615","$715"]]),
    ) + divider("Excepciones activas") + grid(3,
        block("Preescolar", ["Escuela", "2 pzas", "3 pzas"],
              [["Sor Juana Inés de la Cruz","$515","—"]], exc=True),
        block("Primaria", ["Escuela", "2 pzas", "3 pzas"],
              [["Adolfo Lopez Mateo","575/585/595","—"],
               ["Colegio Motolinea","595/630/640/650","695/730/740/750"]], exc=True),
        block("Secundaria · Bachillerato", ["Escuela", "2 pzas", "3 pzas"],
              [["Telesecundaria 454","$650","$750"],["Telesecundaria 512","$650","$750"],
               ["CECYTE","$650","$750"],["Conalep","$650","$750"],
               ["UVEG","$650","$750"]], exc=True),
    ) + notes("Si una escuela aparece en excepciones, respetar ese precio.")
    return page("Pants", "Pants 2 y 3 Piezas", RULE, body)


def build_pants_suelto():
    body = grid(2,
        block("Liso", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$165"],["10, 12, 14, 16","$180"],["28, CH","$205"],
               ["MD","$215"],["GD","$225"],["EXG","$235"]]),
        block("Punto", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$249"],["10, 12, 14, 16","$269"],["28, CH","$309"],
               ["MD, GD","$319"],["EXG","$339"]]),
    ) + notes(
        "Liso y Punto son familias distintas — no mezclar escaleras.",
        "Si una pieza ya tiene precio mayor marcado, se respeta.",
    )
    return page("Pants", "Pants Suelto Básico", RULE, body)


def build_pantalones():
    body = grid(3,
        block("Vestir · colores estándar", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$235"],["10, 12, 14, 16","$245"],
               ["18, 20, 28, 30","$265"],["32, 34","$285"],
               ["36, 38, 40","$295"],["42, 44","$315"]]),
        block("Vestir Gris · Claro y Obscuro", ["Tallas", "Precio"],
              [["4, 6, 8","$235"],["10, 12","$245"],["14, 16","$255"],
               ["18, 20","$265"],["28, 30","$275"],["32, 34","$285"],
               ["36, 38","$295"],["40, 42","$315"]]),
        block("Gales · Azul, Rojo, Verde", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$235"],["10, 12, 14, 16","$245"],
               ["18, 20, 28, 30","$265"],["32, 34","$285"],
               ["36, 38, 40, 42","$295"],["44","$315"]]),
        block("Escocés", ["Tallas", "Precio"],
              [["3, 4, 6, 8","$199"],["10, 12, 14, 16","$235"],
               ["28, 30, 32","$265"]]),
        block("Gabardina Negro", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$219"],["10, 12, 14, 16","$219"]]),
        block("Pata de Gallo", ["Tallas", "Precio"],
              [["4, 6, 8, 10, 12, 14, 16","$235"],
               ["20, 28, 30, 32","$245"],
               ["34, 36, 38, 40, 42","$255"]]),
    ) + divider("Excepciones activas") + grid(1,
        block("Por escuela", ["Escuela", "Tallas", "Precio"],
              [["Margarita Paz Paredes","2, 4, 6, 8 Escocés Oficial","$239"]], exc=True),
    )
    return page("Pantalones", "Pantalones", RULE, body)


def build_faldas():
    body = grid(4,
        block("Gales · Azul, Rojo, Verde", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$195"],["10, 12","$205"],["14, 16","$215"],
               ["28, 30, 32, 34","$225"],["36, 38, 40, 42","$235"],["44","$245"]]),
        block("Vino", ["Tallas", "Precio"],
              [["4, 6, 8","$199"],["10, 12","$205"],["14, 16","$215"],
               ["28, 30, 32, 34","$225"],["36","$235"]]),
        block("Escocés", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$215"],["10, 12, 14, 16","$235"],
               ["28, 30, 32, 34","$245"],["36, 38","$255"],["40, 42","$265"]]),
        block("Gris · Claro y Obscuro", ["Tallas", "Precio"],
              [["4 – 16","$265"],["28, 30, 32, 34","$275"],
               ["36, 38","$285"],["40, 42","$295"]]),
        block("Cuatro Tablas", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$195"],["10, 12, 14, 16","$205"],
               ["28, 30, 32, 34","$225"],["36, 38, 40, 42","$235"]]),
        block("Escolar Azul Marino", ["Tallas", "Precio"],
              [["2 – 16","$195"],["18, 20, 28, 30","$205"],
               ["32, 34","$215"],["36, 38","$225"],["40, 42","$235"]]),
        block("Pgallo Café", ["Tallas", "Precio"],
              [["12, 14, 16","$205"],["28 – 34","$245"],["36 – 42","$255"]]),
        block("Oficial Escolar (genérica)", ["Tallas", "Precio"],
              [["12","$205"],["14, 16","$215"],["28 – 34","$245"],["36 – 42","$255"]]),
        block("Oficial Preescolar Azul", ["Tallas", "Precio"],
              [["Línea completa","$239"]]),
    ) + divider("Excepciones activas") + grid(1,
        block("Por escuela", ["Escuela", "Tallas", "Precio"],
              [["Colegio Motolinea","4–8 / 10–12 / 14–16 / 28–34 / 36–38","$205 / $215 / $225 / $245 / $255"],
               ["SABES","10–16 / 28–34 / 36–38 / 40–42","$270 / $275 / $285 / $295"],
               ["Conalep","14–16 / 28–34 / 36–42","$280 / $285 / $295"],
               ["Margarita Paz Paredes","4, 6, 8 Preescolar","$239"]], exc=True),
    ) + notes("Las faldas por escuela siempre deben estar por encima de la línea genérica.")
    return page("Faldas", "Faldas", RULE, body)


def build_jumper_malla_bata():
    body = grid(3,
        block("Jumper", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$249"],["10, 12, 14, 16","$269"],["28, 30","$289"],
               ["32, 34","$309"],["36, 38","$319"],["40, 42","$329"]]),
        block("Malla Escolar", ["Tallas", "Precio"],
              [["0-0, 0-2, 3-5, 6-8","$109"],["9-12","$129"],
               ["13-18, CH-MD, GD-EXG, Dama","$139"]]),
        block("Bata", ["Tipo", "Tallas", "Precio"],
              [["Infantil","Uni","$65"],["Manga Corta","12 – 46","$395"],
               ["Manga Larga","12 – 46","$439"]]),
    ) + notes("Si una pieza ya tiene precio mayor marcado, se respeta.")
    return page("Jumper · Malla · Bata", "Jumper · Malla · Bata", RULE, body)


def build_accesorios():
    body = grid(2,
        block("Accesorios", ["Pieza", "Precio"],
              [["Calceta Escolar","$49"],["Guante Escolta","$49"],["Corbata","$70"],
               ["Corbatín","$70"],["Moño","$70"],["Boina Escolta","$80"]]),
        block("Playera Polo Blanca", ["Tallas", "Precio"],
              [["2, 4, 6, 8","$135"],["10, 12","$145"],["14, 16, 18","$155"],
               ["28, 30, 32, 34, 36, 38","$170"],["40, 42","$180"],
               ["CH, MD","$185"],["GD, EXG","$195"]]),
    ) + notes("Si una pieza ya tiene precio mayor marcado, se respeta.")
    return page("Accesorios", "Accesorios · Playera Polo", RULE, body)


# ── Generar ───────────────────────────────────────────────────────────────────
PAGES = [
    ("Playeras",          build_playeras),
    ("Sueteres",          build_sueteres),
    ("Chamarras",         build_chamarras),
    ("Chalecos",          build_chalecos),
    ("Camisas",           build_camisas),
    ("Pants_2pz_3pz",     build_pants_2pz),
    ("Pants_Suelto",      build_pants_suelto),
    ("Pantalones",        build_pantalones),
    ("Faldas",            build_faldas),
    ("Jumper_Malla_Bata", build_jumper_malla_bata),
    ("Accesorios_Polo",   build_accesorios),
]

HTML_WRAPPER = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>{css}</style>
</head>
<body>
{body}
</body>
</html>"""


def generate():
    # Completo
    all_pages = "\n".join(fn() for _, fn in PAGES)
    html = HTML_WRAPPER.format(title="Tarifario Rápido 2026", css=CSS, body=all_pages)
    out = OUT / "Tarifario_Completo_2026.html"
    out.write_text(html, encoding="utf-8")
    print(f"Generado: {out}")

    # Individuales
    for name, fn in PAGES:
        html = HTML_WRAPPER.format(
            title=f"Tarifario {name.replace('_', ' ')} 2026",
            css=CSS,
            body=fn(),
        )
        p = OUT / f"Tarifario_{name}_2026.html"
        p.write_text(html, encoding="utf-8")
        print(f"  + {p.name}")


if __name__ == "__main__":
    generate()
