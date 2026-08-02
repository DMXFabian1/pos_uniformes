#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera el HTML del tarifario de escolta MAXIMODA (para convertir a PDF). v2: colores + tablas claras."""
import base64, pathlib
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

BASE = pathlib.Path("/Users/danielfabian/Documents/Playground 2")
LOGO = BASE / "pos_uniformes/assets/customer_card_template/brand/business-logo.png"
OUT = BASE / "tarifarios/tarifario_escolta_maximoda.html"

logo_b64 = base64.b64encode(LOGO.read_bytes()).decode()
FECHA = "Junio 2026"
DESC_PCT = Decimal("8")  # descuento por uniforme completo; el % NO se imprime en el documento


def _round_total(total: Decimal) -> Decimal:
    """Regla de redondeo del POS — réplica de quick_sale_view._round_total /
    sale_rounding_service.resolve_sale_rounding (redondeo a $0.50)."""
    total = Decimal(total).quantize(Decimal("0.01"))
    integer_part = total.to_integral_value(rounding=ROUND_FLOOR)
    cents = (total - integer_part).quantize(Decimal("0.01"))
    if cents <= Decimal("0.19"):
        return integer_part.quantize(Decimal("0.01"))
    if cents <= Decimal("0.69"):
        return (integer_part + Decimal("0.50")).quantize(Decimal("0.01"))
    return (integer_part + Decimal("1.00")).quantize(Decimal("0.01"))


def _nearest_059(n) -> int:
    """Entero más cercano terminado en 0, 5 o 9 (en empate, hacia arriba)."""
    n = Decimal(n)
    D = int(n // 10)
    cands = sorted({dd * 10 + t for dd in (D - 1, D, D + 1) for t in (0, 5, 9) if dd * 10 + t > 0})
    best = None
    for m in cands:
        d = abs(Decimal(m) - n)
        if best is None or d < best[0] or (d == best[0] and m > best[1]):
            best = (d, m)
    return best[1]


def precio_desc(precio) -> Decimal:
    """Precio con descuento por uniforme completo, redondeado a terminación 0/5/9."""
    bruto = Decimal(precio) * (Decimal("100") - DESC_PCT) / Decimal("100")
    return Decimal(_nearest_059(bruto))


def fmt_money(d) -> str:
    d = Decimal(d).quantize(Decimal("0.01"))
    return f"${int(d)}" if d == d.to_integral_value() else f"${d:.2f}"

# Colores de boina (14 únicos) con su muestra hex, agrupados por familia
COLORES_BOINA = [
    ("Blanco", "#ffffff"), ("Beige", "#d8c3a5"), ("Negro", "#1a1a1a"),
    ("Rojo", "#c0392b"), ("Vino", "#6b1f2a"),
    ("Azul rey", "#1f4fd8"), ("Azul marino", "#1b2a4a"),
    ("Verde", "#2e7d32"), ("Verde limón", "#b5d33d"), ("Camuflaje", "#6b7a3f"), ("Café", "#6f4e37"),
]

# Prendas con tabla Talla -> Precio
PRENDAS = [
    ("Camisa Manga Larga Blanca — Caballero", "Blanco · de gala",
     [("2 a 8", 199), ("10 a 18", 219), ("32 a 34", 239), ("36 a 38", 249),
      ("40 a 44 · CH", 259), ("Mediana (MD)", 269), ("Grande (GD)", 279), ("Extra grande (EXG)", 289)]),
    ("Camisa Manga Larga Blanca — Dama", "Blanco · de gala",
     [("Chica (CH)", 279), ("Mediana y grande", 289), ("Extra grande (EXG)", 309)]),
    ("Camisa Manga Corta Blanca", "Blanco · unisex",
     [("4 a 8", 89), ("10 a 16", 99), ("28 a 30", 115), ("32 a 34", 135), ("36 a 38", 145), ("40 a 42", 165)]),
    ("Pantalón de Vestir — Caballero", "Blanco o negro",
     [("2 a 8", 235), ("10 a 16", 245), ("18 a 30", 265), ("32 a 34", 285), ("36 a 40", 295)]),
    ("Falda Escolar — Dama", "Azul marino",
     [("2 a 8", 195), ("10 a 16", 205), ("18 a 34", 225), ("36 a 42", 235)]),
    ("Falda Gris — Dama", "Gris claro u oscuro",
     [("4 a 16", 265), ("28 a 34", 275), ("36 a 38", 285), ("40 a 42", 295)]),
]


def luminancia_oscura(hexcolor):
    r = int(hexcolor[1:3], 16); g = int(hexcolor[3:5], 16); b = int(hexcolor[5:7], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) > 140  # True => fondo claro => texto oscuro


def pill(nombre, hexc):
    borde = "border:1px solid #cfcfcf;" if hexc.lower() in ("#ffffff", "#fff") else "border:1px solid rgba(0,0,0,.08);"
    return f'<div class="cpill"><span class="sw" style="background:{hexc};{borde}"></span>{nombre}</div>'


def tabla(filas):
    rows = "".join(
        f'<tr><td class="tt">{t}</td><td class="tp">${p}</td><td class="td2">{fmt_money(precio_desc(p))}</td></tr>'
        for t, p in filas
    )
    return f'<table class="precios"><tbody>{rows}</tbody></table>'


def tarjeta(nombre, colores, filas):
    return f"""
      <div class="card">
        <div class="card-h"><span class="card-nom">{nombre}</span><span class="card-col">{colores}</span></div>
        {tabla(filas)}
      </div>"""


boina_pills = "".join(pill(n, h) for n, h in COLORES_BOINA)
cards = "".join(tarjeta(*p) for p in PRENDAS)

# ===== Hoja 2: ejemplo de costo + formulario imprimible =====
EJEMPLO = [
    ("Uniforme Caballero", [
        ("Camisa M/Larga Blanca", "talla 10–18", 219),
        ("Pantalón de Vestir", "talla 10–16", 245),
        ("Boina de Escolta", "única", 80),
        ("Guantes de Escolta", "—", 49),
    ], 593),
    ("Uniforme Dama", [
        ("Camisa M/Larga Blanca", "talla CH", 279),
        ("Falda Escolar Azul", "talla 10–16", 205),
        ("Boina de Escolta", "única", 80),
        ("Guantes de Escolta", "—", 49),
    ], 613),
]

FORM = [
    ("Uniforme Caballero", [
        "Camisa Manga Larga Blanca", "Camisa Manga Corta Blanca",
        "Pantalón de Vestir", "Boina de Escolta", "Guantes de Escolta", "Otro:",
    ]),
    ("Uniforme Dama", [
        "Camisa Manga Larga Blanca", "Camisa Manga Corta Blanca",
        "Falda (Azul marino o Gris)", "Boina de Escolta", "Guantes de Escolta", "Otro:",
    ]),
]


def ejemplo_col(titulo, items, total):
    total_desc = sum(int(precio_desc(p)) for _, _, p in items)
    filas = "".join(
        f'<tr><td class="e-pr">{n}<span class="e-meta"> · {meta}</span></td>'
        f'<td class="e-pre">${p}</td><td class="e-pre2">{fmt_money(precio_desc(p))}</td></tr>'
        for n, meta, p in items
    )
    return f"""
      <div class="e-card">
        <div class="e-tit">{titulo}</div>
        <table class="e-tab">
          <tr class="e-head"><td></td><td class="e-pre">Normal</td><td class="e-pre2">Con todo</td></tr>
          {filas}
          <tr class="e-tot"><td>Total</td><td class="e-pre">${total}</td><td class="e-pre2">${total_desc}</td></tr>
        </table>
      </div>"""


def form_table(titulo, items):
    filas = ""
    for it in items:
        filas += f'<tr><td class="f-pr">{it}</td><td></td><td></td><td></td><td></td></tr>'
    return f"""
      <div class="f-block">
        <div class="f-tit">{titulo}</div>
        <table class="f-tab">
          <thead><tr><th class="l">Prenda</th><th>Talla</th><th>P. Unit.</th><th>Cant.</th><th>Importe</th></tr></thead>
          <tbody>{filas}</tbody>
        </table>
      </div>"""


ejemplo_html = "".join(ejemplo_col(*e) for e in EJEMPLO)
form_html = "".join(form_table(*f) for f in FORM)

# ===== Hoja 3: lista de la escolta (matriz estilo panel de uniformes) =====
COLS_PIEZAS = ["M/Larga", "M/Corta", "Pantalón", "Falda", "Boina", "Guantes"]
N_ESCOLTA = 10


def lista_escolta_html():
    ths = "".join(f"<th>{c}</th>" for c in COLS_PIEZAS)
    filas = ""
    for i in range(1, N_ESCOLTA + 1):
        celdas = "".join("<td></td>" for _ in COLS_PIEZAS)
        filas += f'<tr><td class="le-idx">{i}</td><td class="le-nom"></td>{celdas}<td class="le-tot"></td></tr>'
    tot_celdas = "".join("<td></td>" for _ in COLS_PIEZAS)
    fila_tot = (f'<tr class="le-suma"><td></td><td class="le-sumlbl">Total de piezas →</td>'
                f'{tot_celdas}<td class="le-tot"></td></tr>')
    return f"""
      <table class="lista-escolta">
        <thead><tr><th class="le-idx">#</th><th class="le-nom-h">Integrante</th>{ths}<th>Total $</th></tr></thead>
        <tbody>{filas}{fila_tot}</tbody>
      </table>"""


lista_html = lista_escolta_html()

HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
  @page {{ size: Letter; margin: 6mm 14mm; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:"Helvetica Neue",Arial,sans-serif; color:#1a1a1a; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
  :root {{ --navy:#1b2a4a; --gold:#a9884f; --soft:#6b6b6b; --line:#e5e5e5; --bg:#faf9f7; }}

  .top {{ text-align:center; padding-bottom:10px; border-bottom:2px solid var(--navy); }}
  .top img {{ height:44px; }}
  .doc-tipo {{ margin-top:7px; font-family:Didot,"Bodoni 72",Georgia,serif; font-size:18px; letter-spacing:3px; color:var(--navy); text-transform:uppercase; }}
  .doc-sub {{ margin-top:3px; font-size:10.5px; letter-spacing:4px; color:var(--gold); text-transform:uppercase; }}

  /* Boina destacada */
  .boina {{ display:flex; gap:18px; align-items:center; margin-top:11px; padding:10px 16px; background:var(--bg); border:1px solid var(--line); border-radius:10px; break-inside:avoid; }}
  .boina-left {{ flex:0 0 150px; border-right:1px solid var(--line); padding-right:16px; }}
  .boina-left .nom {{ font-size:14px; font-weight:600; }}
  .boina-left .meta {{ font-size:11px; color:var(--soft); margin-top:2px; }}
  .boina-left .precio {{ margin-top:8px; display:inline-block; background:var(--navy); color:#fff; font-size:17px; font-weight:700; padding:5px 18px; border-radius:6px; }}
  .boina-left .precio-desc {{ margin-top:5px; font-size:10.5px; font-weight:700; color:#0f6e56; }}
  .boina-right {{ flex:1; }}
  .boina-right .lab {{ font-size:10px; letter-spacing:2px; text-transform:uppercase; color:var(--gold); margin-bottom:7px; }}
  .colores {{ display:grid; grid-template-columns:repeat(4,1fr); gap:6px 10px; }}
  .cpill {{ display:flex; align-items:center; gap:7px; font-size:11px; color:#333; }}
  .cpill .sw {{ width:15px; height:15px; border-radius:50%; flex:0 0 15px; }}

  .seccion-tit {{ margin:13px 0 8px; font-family:Didot,"Bodoni 72",Georgia,serif; font-size:13px; letter-spacing:2px; text-transform:uppercase; color:var(--navy); border-bottom:1px solid var(--line); padding-bottom:5px; }}

  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:9px; }}
  .card {{ border:1px solid var(--line); border-radius:9px; padding:8px 13px; break-inside:avoid; }}
  .card-h {{ margin-bottom:6px; }}
  .card-nom {{ display:block; font-size:13px; font-weight:600; color:#1a1a1a; }}
  .card-col {{ display:block; font-size:10.5px; color:var(--soft); font-style:italic; margin-top:1px; }}
  table.precios {{ width:100%; border-collapse:collapse; }}
  table.precios td {{ padding:2px 2px; font-size:12px; }}
  table.precios tr:nth-child(even) {{ background:var(--bg); }}
  td.tt {{ color:#444; }}
  td.tp {{ text-align:right; font-weight:700; color:var(--navy); font-size:12.5px; width:56px; }}
  td.td2 {{ text-align:right; font-weight:700; color:#0f6e56; font-size:12.5px; width:58px; }}
  .leyenda-desc {{ font-size:10px; color:var(--soft); margin:-3px 0 8px; }}
  .leyenda-desc .ld-n {{ color:var(--navy); font-weight:600; }}
  .leyenda-desc .ld-d {{ color:#0f6e56; font-weight:600; }}

  /* Guantes simple */
  .guantes {{ margin-top:9px; display:flex; align-items:center; gap:14px; padding:9px 13px; border:1px solid var(--line); border-radius:9px; break-inside:avoid; }}
  .guantes .nom {{ font-size:13px; font-weight:600; }}
  .guantes .meta {{ font-size:11px; color:var(--soft); }}
  .guantes .precio {{ background:var(--navy); color:#fff; font-size:15px; font-weight:700; padding:4px 16px; border-radius:6px; }}
  .precio-desc.g {{ margin-left:auto; font-size:10.5px; font-weight:700; color:#0f6e56; }}

  .pie {{ margin-top:13px; padding-top:10px; border-top:2px solid var(--navy); display:flex; gap:22px; }}
  .pie-col {{ flex:1; }}
  .pie h3 {{ font-size:10px; letter-spacing:2px; text-transform:uppercase; color:var(--gold); margin-bottom:6px; }}
  .pie p {{ font-size:11px; line-height:1.55; color:#333; }}
  .pie .big {{ font-size:14px; font-weight:700; color:var(--navy); }}
  .clabe {{ font-family:"SF Mono",Menlo,monospace; font-size:12px; letter-spacing:1px; font-weight:600; }}
  .nota {{ margin-top:9px; text-align:center; font-size:9.5px; color:var(--soft); letter-spacing:.4px; }}

  /* ===== Hoja 2 ===== */
  .hoja2 {{ break-before:page; }}
  .datos {{ margin-top:13px; display:flex; flex-wrap:wrap; gap:9px 18px; font-size:11.5px; color:#333; }}
  .campo {{ display:flex; align-items:flex-end; gap:5px; white-space:nowrap; flex:1; }}
  .campo.grande {{ flex:1 1 100%; }}
  .linea {{ display:inline-block; border-bottom:1px solid #9a9a9a; height:14px; flex:1; min-width:90px; }}
  .linea.ancha {{ min-width:150px; }}

  .ejemplo {{ display:grid; grid-template-columns:1fr 1fr; gap:11px; }}
  .e-card {{ border:1px solid var(--line); border-radius:9px; padding:9px 13px; }}
  .e-tit {{ font-size:12.5px; font-weight:700; color:var(--navy); margin-bottom:4px; }}
  .e-tab {{ width:100%; border-collapse:collapse; }}
  .e-tab td {{ padding:3px 2px; font-size:11.5px; }}
  .e-pr {{ color:#333; }}
  .e-meta {{ color:var(--soft); font-size:10px; }}
  .e-pre {{ text-align:right; font-weight:600; color:#222; width:46px; white-space:nowrap; }}
  .e-pre2 {{ text-align:right; font-weight:700; color:#0f6e56; width:48px; white-space:nowrap; }}
  .e-head td {{ font-size:8px; text-transform:uppercase; letter-spacing:.3px; font-weight:700; color:var(--soft); padding-bottom:1px; }}
  .e-head .e-pre2 {{ color:#0f6e56; }}
  .e-tot td {{ border-top:1px solid var(--navy); font-weight:700; color:var(--navy); font-size:12.5px; padding-top:5px; }}
  .e-tot .e-pre2 {{ color:#0f6e56; }}
  .e-nota {{ font-size:10px; color:var(--soft); margin-top:6px; font-style:italic; text-align:center; }}

  .f-block {{ margin-top:10px; break-inside:avoid; }}
  .f-tit {{ font-size:12px; font-weight:700; color:var(--navy); margin-bottom:4px; }}
  .f-tab {{ width:100%; border-collapse:collapse; }}
  .f-tab th {{ background:var(--navy); color:#fff; font-size:9px; font-weight:600; letter-spacing:.4px; text-transform:uppercase; padding:5px 4px; text-align:center; }}
  .f-tab th.l {{ text-align:left; }}
  .f-tab td {{ border:1px solid #cfcfcf; height:26px; font-size:11.5px; padding:0 7px; }}
  .f-pr {{ color:#222; width:42%; }}
  .f-ref {{ color:#aaa; font-size:11px; }}

  .totales {{ margin-top:13px; display:flex; gap:24px; justify-content:flex-end; font-size:12.5px; font-weight:600; color:var(--navy); }}
  .t-campo {{ display:flex; align-items:flex-end; gap:6px; }}

  /* ===== Hoja 3: lista de la escolta (matriz estilo panel) ===== */
  .le-leyenda {{ font-size:10.5px; color:#555; margin:13px 0 5px; line-height:1.5; }}
  .lista-escolta {{ width:100%; border-collapse:separate; border-spacing:0; font-size:11px; }}
  .lista-escolta th {{ background:var(--navy); color:#fff; padding:7px 4px; font-size:9px; font-weight:600;
                       text-transform:uppercase; letter-spacing:.4px; white-space:nowrap; text-align:center; }}
  .lista-escolta th.le-nom-h {{ text-align:left; padding-left:10px; }}
  .lista-escolta td {{ border:1px solid #cfcfcf; height:30px; text-align:center; }}
  .lista-escolta .le-idx {{ width:24px; color:var(--soft); }}
  .lista-escolta .le-nom {{ width:152px; }}
  .lista-escolta .le-tot {{ width:66px; background:var(--bg); }}
  .le-suma td {{ background:var(--bg); height:25px; }}
  .le-sumlbl {{ text-align:right; padding-right:8px; font-size:9.5px; font-weight:700; color:var(--navy);
                text-transform:uppercase; letter-spacing:.3px; }}
  .le-resumen {{ margin-top:13px; display:flex; gap:26px; justify-content:flex-end; font-size:12.5px; font-weight:600; color:var(--navy); }}
</style>
</head>
<body>
  <div class="top">
    <img src="data:image/png;base64,{logo_b64}" alt="MAXIMODA">
    <div class="doc-tipo">Tarifario de Uniformes de Escolta</div>
    <div class="doc-sub">Lista de precios · {FECHA}</div>
  </div>

  <div class="boina">
    <div class="boina-left">
      <div class="nom">Boina de Escolta</div>
      <div class="meta">Talla única</div>
      <div class="precio">$80</div>
      <div class="precio-desc">{fmt_money(precio_desc(80))} con uniforme completo</div>
    </div>
    <div class="boina-right">
      <div class="lab">{len(COLORES_BOINA)} colores disponibles</div>
      <div class="colores">{boina_pills}</div>
    </div>
  </div>

  <div class="seccion-tit">Camisas, pantalón y falda — precio según talla</div>
  <div class="leyenda-desc">Cada talla muestra el <span class="ld-n">precio normal</span> y el <span class="ld-d">precio llevando el uniforme completo</span>.</div>
  <div class="grid">{cards}</div>

  <div class="guantes">
    <span class="nom">Guantes de Escolta</span>
    <span class="meta">Color blanco · Tallas 2 a 14</span>
    <span class="precio-desc g">{fmt_money(precio_desc(49))} con uniforme completo</span>
    <span class="precio">$49</span>
  </div>

  <div class="pie">
    <div class="pie-col">
      <h3>Pedidos e informes</h3>
      <p><span class="big">Pedidos por WhatsApp</span><br>
      Atención de lunes a sábado.<br>
      Reserve con anticipación su talla.</p>
    </div>
    <div class="pie-col">
      <h3>Pago por transferencia</h3>
      <p><strong>NU Bank</strong> — Daniel Sánchez<br>
      CLABE: <span class="clabe">6381 8000 0183 1735 99</span><br>
      Concepto: <strong>Uniforme</strong><br>
      Envíe su comprobante por WhatsApp.</p>
    </div>
  </div>

  <div class="nota">El precio en verde aplica al adquirir el uniforme completo con nosotros. Precios vigentes a {FECHA}; sujetos a cambio sin previo aviso.</div>

  <div class="hoja2">
    <div class="top">
      <img src="data:image/png;base64,{logo_b64}" alt="MAXIMODA">
      <div class="doc-tipo">Hoja de Pedido · Uniforme de Escolta</div>
      <div class="doc-sub">Para llenar a mano</div>
    </div>

    <div class="datos">
      <span class="campo grande">Alumno(a): <span class="linea"></span></span>
      <span class="campo">Escuela / Grado: <span class="linea"></span></span>
      <span class="campo">Teléfono: <span class="linea"></span></span>
      <span class="campo">Fecha: <span class="linea"></span></span>
    </div>

    <div class="seccion-tit">Ejemplo de uniforme completo (aprox.)</div>
    <div class="ejemplo">{ejemplo_html}</div>
    <div class="e-nota">La columna <b style="color:#0f6e56">Con todo</b> es el precio al llevar el uniforme completo. El total varía según la talla.</div>

    <div class="seccion-tit">Pedido — anote talla y precio de cada prenda</div>
    {form_html}

    <div class="totales">
      <span class="t-campo">Total: <span class="linea ancha"></span></span>
      <span class="t-campo">Anticipo: <span class="linea"></span></span>
      <span class="t-campo">Saldo: <span class="linea"></span></span>
    </div>

    <div class="nota">Boina $80 y guantes $49 son precio fijo. Las demás prendas varían según talla — consulte el tarifario de la hoja anterior. Pedidos por WhatsApp.</div>
  </div>

  <div class="hoja2">
    <div class="top">
      <img src="data:image/png;base64,{logo_b64}" alt="MAXIMODA">
      <div class="doc-tipo">Lista de la Escolta</div>
      <div class="doc-sub">Control de piezas por integrante</div>
    </div>

    <div class="datos">
      <span class="campo">Escuela: <span class="linea"></span></span>
      <span class="campo">Responsable: <span class="linea"></span></span>
      <span class="campo">Fecha: <span class="linea"></span></span>
    </div>

    <div class="le-leyenda">En cada casilla anota la <b>talla</b> de la prenda (o el <b>color</b> en la boina). Marca <b>✕</b> si esa prenda no aplica al integrante. En <b>Total $</b> anota lo que lleva cada persona.</div>
    {lista_html}

    <div class="le-resumen">
      <span class="t-campo">Integrantes: <span class="linea"></span></span>
      <span class="t-campo">Total del grupo: <span class="linea ancha"></span></span>
    </div>

    <div class="nota">Aplica el precio preferencial cuando el integrante lleva el uniforme completo. Pedidos por WhatsApp.</div>
  </div>
</body>
</html>"""

OUT.write_text(HTML, encoding="utf-8")
print("HTML escrito:", OUT, "·", len(HTML), "bytes")
