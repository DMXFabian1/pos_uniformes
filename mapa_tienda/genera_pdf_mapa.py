#!/usr/bin/env python3
"""Genera un HTML imprimible bonito del mapa de la tienda: una página por piso."""
import json, sys, html, re

ENTRADA = "/Users/danielfabian/Downloads/mapa-tienda-9.json"
SALIDA = sys.argv[1] if len(sys.argv) > 1 else "mapa_print.html"
import datetime
MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
_h = datetime.date.today()
FECHA = f"{_h.day} de {MESES[_h.month-1]} de {_h.year}"

COLORES = {
    "gondola": ("#4F46E5", "Góndola"), "rack": ("#0D9488", "Rack"),
    "tubular": ("#64748B", "Tubular"), "cascada": ("#C026D3", "Cascada"),
    "estanteria": ("#15803D", "Estantería"), "vitrina": ("#DB2777", "Vitrina"),
    "mostrador": ("#F97316", "Mostrador"), "mesa": ("#CA8A04", "Mesa"),
    "probador": ("#7C3AED", "Probador"), "caja": ("#A16207", "Caja"),
    "escalera": ("#0891B2", "Escalera"), "columna": ("#57534E", "Columna"),
}

with open(ENTRADA) as f:
    data = json.load(f)

# área disponible para el plano (carta vertical, dejando lugar a cabecera/leyendas)
ANCHO_PX, ALTO_PX = 720, 700


def rects_de(p):
    return p.get("partes") or [{"x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"]}]


def abrevia(label):
    num = (re.search(r"(\d+)\s*$", label) or [None, ""])[1]
    palabras = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+", label)
    letras = "".join(w[0] for w in palabras[:2]).upper()
    return letras + num


paginas = []
total = len(data["pisos"])
for num_piso, piso in enumerate(data["pisos"], 1):
    xs, ys = [], []
    for k in piso["walls"] + piso["doors"]:
        x, y = map(int, k.split(","))
        xs += [x, x + 1]; ys += [y, y + 1]
    for p in piso["pieces"]:
        for r in rects_de(p):
            xs += [r["x"], r["x"] + r["w"]]; ys += [r["y"], r["y"] + r["h"]]
    for s in piso.get("sectores", []):
        xs += [s["x"], s["x"] + s["w"]]; ys += [s["y"], s["y"] + s["h"]]
    if not xs:
        continue
    x0, y0 = max(0, min(xs) - 1), max(0, min(ys) - 1)
    x1, y1 = max(xs) + 1, max(ys) + 1
    ncols, nrows = x1 - x0, y1 - y0
    cell = min(ANCHO_PX / ncols, ALTO_PX / nrows)

    def px(v):
        return round(v * cell, 1)

    h = []
    h.append(f'<div class="lienzo" style="width:{px(ncols)}px;height:{px(nrows)}px;'
             f'background-size:{cell}px {cell}px">')

    # 1) zonas: fondo + nombre grande centrado (marca de agua)
    for s in piso.get("sectores", []):
        w_px, h_px = px(s["w"]), px(s["h"])
        nombre = s["nombre"]
        fs = max(11, min(34, w_px / (len(nombre) * 0.62), h_px * 0.45))
        h.append(
            f'<div class="sector" style="left:{px(s["x"]-x0)}px;top:{px(s["y"]-y0)}px;'
            f'width:{w_px}px;height:{h_px}px;background:{s["color"]}1c;border-color:{s["color"]}">'
            f'<span class="agua" style="color:{s["color"]}59;font-size:{fs}px">{html.escape(nombre.upper())}</span></div>')

    # 2) paredes y puertas
    for k in piso["walls"]:
        x, y = map(int, k.split(","))
        h.append(f'<div class="pared" style="left:{px(x-x0)}px;top:{px(y-y0)}px;'
                 f'width:{px(1)}px;height:{px(1)}px"></div>')
    for k in piso["doors"]:
        x, y = map(int, k.split(","))
        h.append(f'<div class="puerta" style="left:{px(x-x0)}px;top:{px(y-y0)}px;'
                 f'width:{px(1)}px;height:{px(1)}px"></div>')

    # 3) piezas con etiqueta inteligente
    for p in piso["pieces"]:
        color = COLORES.get(p["tipo"], ("#64748B",))[0]
        for i, r in enumerate(rects_de(p)):
            w_px, h_px = px(r["w"]), px(r["h"])
            etiqueta = ""
            if i == 0 and p["tipo"] != "columna":
                vertical = r["h"] > r["w"] and w_px < 42
                largo_disp = (h_px if vertical else w_px) - 6
                fs = max(6.5, min(10.5, cell * 0.42))
                texto = p["label"]
                if len(texto) * fs * 0.58 > largo_disp:
                    texto = abrevia(texto)
                    fs = max(6, min(fs, largo_disp / (len(texto) * 0.62)))
                clase = "pl vert" if vertical else "pl"
                etiqueta = (f'<span class="{clase}" style="font-size:{fs:.1f}px">'
                            f'{html.escape(texto)}</span>')
            h.append(f'<div class="pieza" style="left:{px(r["x"]-x0)}px;top:{px(r["y"]-y0)}px;'
                     f'width:{w_px}px;height:{h_px}px;background:{color}">{etiqueta}</div>')

    # 4) chips de zona ENCIMA de todo (no los tapan los muebles)
    for s in piso.get("sectores", []):
        cx = min(max(px(s["x"] - x0) + 4, 4), px(ncols) - 90)
        cy = min(max(px(s["y"] - y0) + 4, 4), px(nrows) - 18)
        h.append(f'<span class="chip" style="left:{cx}px;top:{cy}px;'
                 f'background:{s["color"]}">{html.escape(s["nombre"])}</span>')
    h.append('</div>')

    # leyendas
    ley_zonas = "".join(
        f'<span class="ley"><i style="background:{s["color"]}"></i>{html.escape(s["nombre"])}</span>'
        for s in piso.get("sectores", []))
    tipos_usados = []
    for p in piso["pieces"]:
        if p["tipo"] not in tipos_usados:
            tipos_usados.append(p["tipo"])
    ley_tipos = "".join(
        f'<span class="ley"><i style="background:{COLORES[t][0]}"></i>{COLORES[t][1]}</span>'
        for t in tipos_usados if t in COLORES)

    ancho_m = ncols * 0.5
    alto_m = nrows * 0.5
    paginas.append(f'''
<section class="pagina">
  <header class="cab">
    <div class="cab-icono"><svg viewBox="0 0 24 24"><path d="M3 9.5 5 4h14l2 5.5" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/><path d="M4 9.5v10h16v-10" fill="none" stroke="#fff" stroke-width="1.8"/><path d="M9 19.5v-6h6v6" fill="none" stroke="#fff" stroke-width="1.8"/></svg></div>
    <div>
      <h1>Mapa de la Tienda — {html.escape(piso["nombre"])}</h1>
      <p class="sub">{FECHA} · {len(piso["pieces"])} piezas · {ancho_m:.0f} × {alto_m:.0f} m aprox · 1 celda ≈ 50 cm</p>
    </div>
    <div class="escala"><i style="width:{px(2)}px"></i><span>1 m</span></div>
  </header>
  <div class="mapa-wrap">{"".join(h)}</div>
  <div class="pie-leyendas">
    {f'<div class="fila-ley"><b>Zonas</b>{ley_zonas}</div>' if ley_zonas else ''}
    <div class="fila-ley"><b>Muebles</b>{ley_tipos}</div>
  </div>
  <footer class="pie">Hoja {num_piso} de {total}</footer>
</section>''')

pagina_html = f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Mapa de la Tienda</title>
<link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600&family=Nunito:wght@700;800&display=swap" rel="stylesheet">
<style>
@page {{ size: letter portrait; margin: 9mm; }}
* {{ box-sizing: border-box; margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
body {{ font-family: 'Nunito', -apple-system, sans-serif; color: #1E1B4B; }}
.pagina {{ page-break-after: always; display: flex; flex-direction: column; height: 258mm; }}
.pagina:last-child {{ page-break-after: auto; }}

.cab {{ display: flex; align-items: center; gap: 12px; background: #4F46E5;
  border-radius: 12px; padding: 10px 16px; color: #fff; margin-bottom: 10px; }}
.cab-icono {{ width: 34px; height: 34px; flex-shrink: 0; }}
.cab h1 {{ font-family: 'Fredoka', 'Nunito', sans-serif; font-size: 19px; font-weight: 600; }}
.sub {{ font-size: 10px; opacity: 0.85; margin-top: 1px; }}
.escala {{ margin-left: auto; display: flex; align-items: center; gap: 6px; font-size: 10px; font-weight: 800; }}
.escala i {{ display: block; height: 5px; background: #fff; border-radius: 3px; }}

.mapa-wrap {{ flex: 1; display: flex; align-items: center; justify-content: center; }}
.lienzo {{ position: relative; border: 2px solid #C7D2FE; border-radius: 6px;
  background-color: #FDFDFF;
  background-image: linear-gradient(to right, #EEF1FA 0.5px, transparent 0.5px),
    linear-gradient(to bottom, #EEF1FA 0.5px, transparent 0.5px);
  background-origin: border-box; overflow: hidden; }}
.lienzo > * {{ position: absolute; }}

.pared {{ background: #6E6862; }}
.puerta {{ background: repeating-linear-gradient(45deg, #BAE6FD, #BAE6FD 3px, #7DD3FC 3px, #7DD3FC 6px);
  border: 1px solid #0EA5E9; }}

.sector {{ border: 1.5px dashed; border-radius: 8px; display: flex;
  align-items: center; justify-content: center; overflow: hidden; }}
.agua {{ font-family: 'Fredoka', sans-serif; font-weight: 600; letter-spacing: 2px;
  white-space: nowrap; }}
.chip {{ color: #fff; font-size: 8.5px; font-weight: 800; padding: 2px 8px;
  border-radius: 999px; border: 1.5px solid rgba(255,255,255,0.75);
  box-shadow: 0 1px 2px rgba(0,0,0,0.25); white-space: nowrap; }}

.pieza {{ border-radius: 4px; display: flex; align-items: center; justify-content: center;
  overflow: hidden; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.45), inset 0 -2px 0 rgba(0,0,0,0.12); }}
.pl {{ color: #fff; font-weight: 800; text-align: center; line-height: 1.05;
  text-shadow: 0 1px 1px rgba(0,0,0,0.45); white-space: nowrap; }}
.pl.vert {{ writing-mode: vertical-rl; }}

.pie-leyendas {{ margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }}
.fila-ley {{ display: flex; align-items: center; flex-wrap: wrap; gap: 5px 10px;
  font-size: 9px; }}
.fila-ley b {{ font-size: 9px; text-transform: uppercase; letter-spacing: 1px;
  color: #64748B; margin-right: 2px; }}
.ley {{ display: inline-flex; align-items: center; gap: 4px; font-weight: 800; }}
.ley i {{ width: 9px; height: 9px; border-radius: 3px; display: inline-block; }}
.pie {{ margin-top: 5px; font-size: 8.5px; color: #94A3B8; text-align: right; }}
</style></head><body>{"".join(paginas)}</body></html>'''

with open(SALIDA, "w") as f:
    f.write(pagina_html)
print(f"OK: {SALIDA} ({len(paginas)} páginas)")
