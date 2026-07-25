#!/usr/bin/env python3
"""Tarifario por escuela (documento único), con precios leídos de la DB.

Una hoja por (nivel, escuela), ordenadas Preescolar → Primaria → Secundaria →
Bachillerato y alfabético dentro de cada nivel. Cada hoja separa:
  · Uniforme oficial (azul)  · Deportivo (naranja)
Cierra con una hoja de genéricos (accesorios, malla, bata) común a todas.

Reusa datos, escaleras y renderers de generar_tarifarios_db.py.
"""
import re
from collections import defaultdict

import generar_tarifarios_db as G
import generar_tarifarios_html as base

OUT = G.OUT_HTML / "Tarifario_Escuelas_2026.html"
NIVELES = ["Preescolar", "Primaria", "Secundaria", "Bachillerato", "Otros"]

G.DIV_CLASS.setdefault("uniforme oficial", "d-general")
G.DIV_CLASS.setdefault("deportivo", "d-nivel")
G.DIV_CLASS.setdefault("articulos enlazados", "d-general")
G.DIV_CLASS.setdefault("basicos para todas las escuelas", "d-general")
G.DIV_CLASS.setdefault("indice", "d-general")

CACHE_LINKS = G.HERE / "tarifarios_cache_links.json"


def cargar_links():
    """[(escuela, producto_nombre)] desde catalog_school_product_link (con cache)."""
    import json
    try:
        import psycopg
        import os
        G.cargar_env()
        conn = psycopg.connect(
            host=os.environ["POS_UNIFORMES_DB_HOST"], port=5432,
            dbname="pos_uniformes", user="postgres",
            password=os.environ.get("POS_UNIFORMES_DB_PASSWORD", ""),
            connect_timeout=10)
        cur = conn.cursor()
        cur.execute("""
            select e.nombre, p.nombre
            from catalog_school_product_link l
            join escuela e on e.id = l.escuela_id
            join producto p on p.id = l.producto_id
            where l.activo and e.activo and p.activo
        """)
        links = cur.fetchall()
        conn.close()
        CACHE_LINKS.write_text(json.dumps(links), encoding="utf-8")
        return links
    except Exception as exc:
        if CACHE_LINKS.exists():
            print(f"AVISO: DB inaccesible ({exc}); usando cache de links")
            return [tuple(x) for x in json.loads(CACHE_LINKS.read_text(encoding="utf-8"))]
        raise


def limpiar(prod, esc):
    """Nombre de producto sin el nombre de la escuela ni etiquetas.

    La comparación ignora acentos (p.ej. producto "Alvaro Obregon" con
    escuela "Álvaro Obregón").
    """
    b = prod.split("|")[0].strip()
    if esc:
        ne = G.nrm(esc)
        while True:
            i = G.nrm(b).find(ne)
            if i < 0:
                break
            b = b[:i] + b[i + len(esc):]
    b = re.sub(r"\bad hoc\b", "", b, flags=re.I)
    b = re.sub(r"\s+", " ", b).strip(" -·")
    return b or prod.split("|")[0].strip()


_LETRAS_VENTANA = {"CH", "CH-MD", "MD", "GD", "GD-EXG", "EXG"}


def en_ventana(nivel, talla):
    """Ventana de tallas usuales por nivel (acordada con Daniel 2026-07-23)."""
    t = G.talla_norm(talla)
    if t.isdigit():
        n = int(t)
        return {
            "Preescolar": 2 <= n <= 10,
            "Primaria": 4 <= n <= 16 or 28 <= n <= 40,
            "Secundaria": 12 <= n <= 16 or 28 <= n <= 40,
            "Bachillerato": 14 <= n <= 16 or 30 <= n <= 44,
        }.get(nivel, True)
    # tallas con letra: en todos los niveles menos preescolar
    if t in _LETRAS_VENTANA:
        return nivel != "Preescolar"
    return nivel not in ("Preescolar",)


# escuelas donde el suéter de botones es unisex (no va en rosa)
BOTONES_UNISEX = ("Margarita Paz Paredes", "SABES")


def estilo_bloque(nombre, esc):
    """'rosa' para prendas de niña: falda, jumper y suéter de botones."""
    t = G.nrm(nombre)
    if t.startswith("falda") or t.startswith("jumper") or t.startswith("camisa cuello olan"):
        return "rosa"
    if "botones" in t and esc not in BOTONES_UNISEX:
        return "rosa"
    return ""


def orden_oficial(titulo):
    """Orden Daniel: suéter, playera (polo/oficial), camisa, chaleco, falda,
    jumper, (resto), pantalón al final."""
    t = G.nrm(titulo)
    if t.startswith("sueter"):
        return (0, t)
    if t.startswith("chaleco"):
        return (1, t)
    if t.startswith("playera"):
        return (2, t)
    if t.startswith("camisa"):
        return (3, t)
    if t.startswith("falda"):
        return (4, t)
    if t.startswith("jumper"):
        return (5, t)
    if t.startswith("pantalon"):
        return (9, t)
    return (6, t)


def orden_deportivo(titulo):
    """Orden pedido por Daniel: 3pz, 2pz, chamarra, suelto y al final playera."""
    t = G.nrm(titulo)
    if t.startswith("pants 3pz"):
        return (0, t)
    if t.startswith("pants 2pz"):
        return (1, t)
    if "chamarra" in t:
        return (2, t)
    if t.startswith("pants suelto"):
        return (3, t)
    if "playera" in t:
        return (4, t)
    return (5, t)


def es_deportivo(nombres_completos):
    txt = " ".join(nombres_completos).lower()
    return "deportiv" in txt or "pants" in txt


def paginas_escuelas(filas):
    por = defaultdict(list)  # (nivel, escuela) -> filas
    por_producto = defaultdict(list)  # nombre completo -> filas (para enlazados)
    for p, e, n, t, pr in filas:
        if e:
            por[(n if n in NIVELES else "Otros", e)].append((p, e, t, pr))
        por_producto[p].append((p, e, t, pr))
    links = defaultdict(set)  # escuela -> nombres de producto enlazados
    for esc, prod in cargar_links():
        links[esc].add(prod)

    # escuelas fuera de la carpeta (Narciso Mendoza estuvo excluida el 2026-07-23
    # y se restauró el 2026-07-24 a pedido de Daniel)
    ESCUELAS_EXCLUIDAS = set()

    P = []
    for nivel in NIVELES:
        claves = sorted((k for k in por if k[0] == nivel), key=lambda k: G.nrm(k[1]))
        for _, esc in claves:
            if esc in ESCUELAS_EXCLUIDAS:
                continue
            por_prod = defaultdict(list)
            for p, e, t, pr in por[(nivel, esc)]:
                por_prod[limpiar(p, esc)].append((p, e, t, pr))
            bl_of, bl_dep = [], []
            for nombre in sorted(por_prod, key=G.nrm):
                filas_v = [f for f in por_prod[nombre] if en_ventana(nivel, f[2])]
                if not filas_v:
                    continue
                rows, _ = G.escalera(filas_v)
                if es_deportivo([f[0] for f in por_prod[nombre]]):
                    # chamarras deportivas fuera del tarifario por escuela
                    # (pedido de Daniel 2026-07-23)
                    if "chamarra" in G.nrm(nombre):
                        continue
                    bl_dep.append((nombre, ["Tallas", "Precio"], rows, "nivel"))
                else:
                    bl_of.append((nombre, ["Tallas", "Precio"], rows, estilo_bloque(nombre, esc)))
            # artículos genéricos enlazados (catálogo del kiosko): la ropa se
            # integra a Oficial/Deportivo; los accesorios se omiten
            OMITIR = ("mono", "corbat", "boina", "guante", "calceta", "malla", "mascada")
            # exclusiones puntuales por escuela (solo del tarifario; el link
            # del catálogo del kiosko no se toca)
            EXCLUIR = {
                ("Ignacio Zaragoza", "pants suelto punto doble raya"),
                ("Ignacio Zaragoza", "chamarra liso azul marino"),
                ("Ignacio Zaragoza", "chamarra punto azul marino"),
                ("Ignacio Zaragoza", "pants suelto liso blanca"),
            }
            vistos = set()
            for prod in sorted(links.get(esc, ()), key=G.nrm):
                nombre = prod.split("|")[0].strip()
                if nombre in vistos or prod not in por_producto:
                    continue
                if any(G.nrm(nombre).startswith(o) for o in OMITIR):
                    continue
                if (esc, G.nrm(nombre)) in EXCLUIR:
                    continue
                vistos.add(nombre)
                filas_p = [f for f in por_producto[prod] if en_ventana(nivel, f[2])]
                if not filas_p:
                    continue
                rows, _ = G.escalera(filas_p)
                if es_deportivo([prod]):
                    if "chamarra" in G.nrm(nombre):
                        continue
                    bl_dep.append((nombre, ["Tallas", "Precio"], rows, "nivel"))
                else:
                    bl_of.append((nombre, ["Tallas", "Precio"], rows, estilo_bloque(nombre, esc)))
            bl_of.sort(key=lambda b: orden_oficial(b[0]))
            bl_dep.sort(key=lambda b: orden_deportivo(b[0]))
            items = []
            if bl_dep:
                items += [("divider", "Deportivo"), ("grid", 4, bl_dep)]
            if bl_of:
                items += [("divider", "Uniforme oficial"), ("grid", 4, bl_of)]
            P.append((nivel, esc, items))

    # hoja final: genéricos comunes
    F = G.Filas(filas)
    rows_acc = []
    for titulo, fn in [
        ("Calceta Escolar", lambda b_, p, e_, n: b_.startswith("calceta escolar")),
        ("Guante Escolta", lambda b_, p, e_, n: b_.startswith("guante escolta")),
        ("Corbata", lambda b_, p, e_, n: b_.startswith("corbata") and not e_),
        ("Corbatín", lambda b_, p, e_, n: b_.startswith("corbatin") and not e_),
        ("Moño", lambda b_, p, e_, n: b_.startswith("mono ")),
        ("Boina Escolta", lambda b_, p, e_, n: b_.startswith("boina escolta")),
    ]:
        sel = F.sel(fn)
        if sel:
            r, _ = G.escalera(sel)
            rows_acc.append([titulo, " / ".join(pr for _, pr in r)])
    bl = [("Accesorios", ["Pieza", "Precio"], rows_acc)]
    for titulo, fn in [
        ("Malla Escolar", lambda b_, p, e_, n: b_.startswith("malla escolar")),
        ("Playera Polo Blanca", lambda b_, p, e_, n: b_ == "playera polo blanca"),
    ]:
        sel = F.sel(fn)
        if sel:
            r, _ = G.escalera(sel)
            bl.append((titulo, ["Tallas", "Precio"], r))
    rows_bata = []
    for titulo, fn in [
        ("Infantil", lambda b_, p, e_, n: b_.startswith("bata infantil")),
        ("Manga Corta", lambda b_, p, e_, n: b_.startswith("bata manga corta")),
        ("Manga Larga", lambda b_, p, e_, n: b_.startswith("bata manga larga")),
    ]:
        sel = F.sel(fn)
        if sel:
            r, _ = G.escalera(sel)
            for tallas, precio in r:
                rows_bata.append([titulo, tallas, precio])
    if rows_bata:
        bl.append(("Bata", ["Tipo", "Tallas", "Precio"], rows_bata))
    P.append(("Básicos", "Básicos para todas las escuelas",
              [("divider", "Básicos para todas las escuelas"), ("grid", 3, bl)]))
    return P


CSS_LOCAL = """
/* este documento es más denso: escala de impresión por hoja (auto-ajuste) */
@media print {
  .page {
    zoom: var(--pz, 0.95);
    width: calc(297mm / var(--pz, 0.95));
    /* alto casi-A4 (compensado por zoom) para que el numero quede al pie
       de la hoja fisica sin derramar pagina fantasma */
    min-height: calc(205mm / var(--pz, 0.95));
  }
}
.page { position: relative; }

.pagina-num {
  position: absolute; bottom: 10px; right: 20px;
  font-size: 10px; font-weight: 700; color: #94A3B8;
}
"""

AUTOFIT_JS = """
<script>
// asigna a cada hoja el zoom de impresión justo para caber en un A4 horizontal
(function () {
  var objetivo = 210 * 96 / 25.4;  // alto A4 en px CSS
  document.querySelectorAll('.page').forEach(function (p) {
    var z = Math.min(0.95, (objetivo / p.offsetHeight) * 0.97);
    p.style.setProperty('--pz', Math.max(0.5, z).toFixed(3));
  });
})();
</script>
"""


def con_numero(html_pagina, num):
    """Inserta el número de página antes del cierre de la hoja."""
    html_pagina = html_pagina.rstrip()
    assert html_pagina.endswith("</div>")
    return html_pagina[:-6] + f'<div class="pagina-num">Página {num}</div></div>'


def generate():
    G.DOC_NOMBRE = "Tarifario por Escuela"
    filas = G.cargar_filas()
    P = paginas_escuelas(filas)

    # secuencia final: índice por nivel + sus hojas; genéricos al final
    CON_INDICE = ("Preescolar", "Primaria", "Secundaria", "Bachillerato")
    secuencia = []  # (tipo, nivel, titulo, items)
    # tarifario general al inicio (pedido de Daniel 2026-07-23)
    for _name, cat, tit, items_g in G.paginas(G.Filas(filas)):
        secuencia.append(("pagina", cat, tit, items_g))
    # luego básicos
    secuencia += [("pagina",) + pg for pg in P
                  if pg[0] not in CON_INDICE + ("Otros",)]
    for nivel in CON_INDICE + ("Otros",):
        grupo = [pg for pg in P if pg[0] == nivel]
        if not grupo:
            continue
        if nivel in CON_INDICE:
            secuencia.append(("indice", nivel, f"Índice · {nivel}", None))
        secuencia += [("pagina",) + pg for pg in grupo]

    # numeración secuencial (los índices también cuentan)
    numerada = [(i + 1, *item) for i, item in enumerate(secuencia)]

    html_pages = []
    for num, tipo, nivel, titulo, items in numerada:
        if tipo == "indice":
            rows = [[t2, str(n2)] for n2, tp2, nv2, t2, _ in numerada
                    if tp2 == "pagina" and nv2 == nivel]
            items = [("divider", "Índice"),
                     ("grid", 2, [(f"Escuelas de {nivel}", ["Escuela", "Página"], rows)])]
        html_pages.append(con_numero(G.html_page(nivel, titulo, items), num))

    html = base.HTML_WRAPPER.format(
        title="Tarifario por Escuela 2026", css=base.CSS + G.CSS_EXTRA + CSS_LOCAL,
        body="\n".join(html_pages) + AUTOFIT_JS)
    OUT.write_text(html, encoding="utf-8")
    print(f"Generado: {OUT} ({len(numerada)} hojas, {len(numerada) - len(P)} índices)")


if __name__ == "__main__":
    generate()
