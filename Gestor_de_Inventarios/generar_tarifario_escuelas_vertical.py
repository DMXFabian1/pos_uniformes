#!/usr/bin/env python3
"""Tarifario por escuela — versión VERTICAL (A4 retrato) con espacio para foto.

Mismo contenido que la versión horizontal (generar_tarifario_escuelas_db.py):
índices por nivel, numeración, ventanas de tallas, colores 2024. Cada hoja de
escuela lleva un recuadro para foto bajo el encabezado; si existe
fotos_escuelas/<Escuela>.jpg|png se incrusta automáticamente.
"""
import base64

import generar_tarifario_escuelas_db as E
import generar_tarifarios_db as G
import generar_tarifarios_html as base

OUT = G.OUT_HTML / "Tarifario_Escuelas_Vertical_2026.html"
FOTOS = G.HERE / "fotos_escuelas"

CSS_V = """
/* ── Versión vertical: A4 retrato ── */
@page { size: A4 portrait; margin: 0; }
.page { width: 210mm; min-height: 297mm; position: relative; }
@media print {
  .page {
    zoom: var(--pz, 0.95);
    width: calc(210mm / var(--pz, 0.95));
    min-height: calc(292mm / var(--pz, 0.95));
    height: auto;
  }
}
.pagina-num {
  position: absolute; bottom: 10px; right: 20px;
  font-size: 10px; font-weight: 700; color: #94A3B8;
}
.foto-slot {
  height: 88mm; margin-bottom: 12px;
  border: 2px dashed #9DB4C8; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: #8CA3B8; font-weight: 700; letter-spacing: 1.5px; font-size: 13px;
  overflow: hidden;
}
.foto-slot img { width: 100%; height: 100%; object-fit: contain; }
"""

AUTOFIT_JS = """
<script>
// Escala GLOBAL: todas las hojas usan el mismo zoom (el que pida la más densa),
// para que la foto y las tablas queden del mismo tamaño en toda impresión
// a doble cara.
(function () {
  var objetivo = 292 * 96 / 25.4;  // alto A4 vertical en px CSS
  var conFoto = [], otras = [];
  document.querySelectorAll('.page').forEach(function (p) {
    (p.querySelector('.foto-slot') ? conFoto : otras).push(p);
  });
  // hojas con foto: escala uniforme (doble cara)
  var z = 0.95;
  conFoto.forEach(function (p) { z = Math.min(z, (objetivo / p.offsetHeight) * 0.97); });
  z = Math.max(0.45, z);
  conFoto.forEach(function (p) { p.style.setProperty('--pz', z.toFixed(3)); });
  // el resto (general, índices, básicos): ajuste individual
  otras.forEach(function (p) {
    var zi = Math.min(0.95, (objetivo / p.offsetHeight) * 0.97);
    p.style.setProperty('--pz', Math.max(0.45, zi).toFixed(3));
  });
})();
</script>
"""


def foto_html(esc):
    for ext in ("jpg", "jpeg", "png"):
        f = FOTOS / f"{esc}.{ext}"
        if f.exists():
            b64 = base64.b64encode(f.read_bytes()).decode()
            mime = "png" if ext == "png" else "jpeg"
            return f'<div class="foto-slot"><img src="data:image/{mime};base64,{b64}"></div>'
    return '<div class="foto-slot">FOTO DEL UNIFORME</div>'


def a_columnas(items, cols):
    """Reacomoda las secciones al número de columnas del formato vertical.

    Las excepciones (3 columnas internas) van a máximo 2 por fila para que
    las tallas no se apilen.
    """
    out = []
    for it in items:
        if it[0] == "grid_exc":
            out.append((it[0], min(2, it[1]), it[2]))
        elif it[0] == "grid":
            out.append((it[0], min(cols, it[1]), it[2]))
        else:
            out.append(it)
    return out


def pagina_v(category, title, items, foto, num):
    cuerpo = ""
    for item in items:
        if item[0] == "divider":
            cls = G.DIV_CLASS.get(G.nrm(item[1]), "")
            cuerpo += (f'<div class="divider {cls}">{item[1]}</div>' if cls
                       else base.divider(item[1]))
        else:
            kind, cols, blocks = item
            cuerpo += base.grid(cols, *[G.html_block(b, exc=(kind == "grid_exc"))
                                        for b in blocks])
    return f"""
<div class="page">
  <div class="page-header">
    <div class="header-left">
      <div class="header-category">Catálogo Escolar · {category}</div>
      <div class="header-title">{title}</div>
    </div>
    <div class="header-right">
      <div class="header-date">Actualizado: {G.FECHA}</div>
    </div>
  </div>
  {foto}
  {cuerpo}
  <div class="pagina-num">Página {num}</div>
</div>"""


def generate():
    FOTOS.mkdir(exist_ok=True)
    filas = G.cargar_filas()
    P = E.paginas_escuelas(filas)

    CON_INDICE = ("Preescolar", "Primaria", "Secundaria", "Bachillerato")
    secuencia = []
    # tarifario general al inicio (pedido de Daniel 2026-07-23)
    for _name, cat, tit, items_g in G.paginas(G.Filas(filas)):
        secuencia.append(("pagina", cat, tit, items_g))
    secuencia += [("pagina",) + pg for pg in P
                  if pg[0] not in CON_INDICE + ("Otros",)]
    for nivel in CON_INDICE + ("Otros",):
        grupo = [pg for pg in P if pg[0] == nivel]
        if not grupo:
            continue
        if nivel in CON_INDICE:
            secuencia.append(("indice", nivel, f"Índice · {nivel}", None))
        secuencia += [("pagina",) + pg for pg in grupo]

    numerada = [(i + 1, *item) for i, item in enumerate(secuencia)]
    html_pages = []
    con_foto = 0
    for num, tipo, nivel, titulo, items in numerada:
        if tipo == "indice":
            rows = [[t2, str(n2)] for n2, tp2, nv2, t2, _ in numerada
                    if tp2 == "pagina" and nv2 == nivel]
            items = [("divider", "Índice"),
                     ("grid", 2, [(f"Escuelas de {nivel}", ["Escuela", "Página"], rows)])]
            foto = ""
        elif nivel in CON_INDICE + ("Otros",):
            foto = foto_html(titulo)
            con_foto += "img" in foto
        else:
            foto = ""  # básicos e índices van sin foto
        cols = 2 if tipo == "indice" else 3
        html_pages.append(pagina_v(nivel, titulo, a_columnas(items, cols), foto, num))

    html = base.HTML_WRAPPER.format(
        title="Catálogo Escolar 2026",
        css=base.CSS + G.CSS_EXTRA + CSS_V,
        body="\n".join(html_pages) + AUTOFIT_JS)
    OUT.write_text(html, encoding="utf-8")
    print(f"Generado: {OUT} ({len(numerada)} hojas, {con_foto} con foto real)")


if __name__ == "__main__":
    generate()
