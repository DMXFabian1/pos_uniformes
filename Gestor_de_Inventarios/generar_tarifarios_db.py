#!/usr/bin/env python3
"""Genera tarifarios (HTML y Word) con precios leídos de la DB de producción.

A diferencia de generar_tarifarios_html.py (precios hardcodeados), aquí cada
escalera se deriva de variante.precio_venta: el precio modal por talla forma la
escalera principal y todo lo que se desvía cae al bloque de Excepciones.

Uso:
    python generar_tarifarios_db.py           # HTML + Word
    python generar_tarifarios_db.py --html    # solo HTML
    python generar_tarifarios_db.py --docx    # solo Word
"""
import os
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import generar_tarifarios_html as base

HERE = Path(__file__).parent
OUT_HTML = HERE / "tarifarios_html"
OUT_DOCX = HERE / "tarifarios"
FECHA = "Julio 2026 · precios del sistema"
DOC_NOMBRE = "Tarifario General"  # los otros generadores lo sobreescriben

# CSS adicional: esquema de colores estilo Carpeta 2024 + secciones
CSS_EXTRA = """
/* Encabezado de hoja: recuadro transparente con letras negras */
.page-header {
  background: none; box-shadow: none;
  border: 2px solid #22303F; border-radius: 10px;
}
.page-header::before { display: none; }
.header-category { color: #555C66; }
.header-title { color: #111111; }
.header-date { color: #777F88; }
/* Títulos de producto: azul cielo 2024 */
.block-title {
  background: #66CCF9;
  color: #093A54;
  border-left: 3px solid #1B9AD6;
}
/* Barras Tallas/Precio: verde 2024 */
thead th {
  background: #A8D08D;
  color: #1E4620;
  border-bottom-color: #8DBE6E;
}
/* Separadores por tipo de sección */
.divider.d-general { color: #0F7DB5; }
.divider.d-general::after { background: #66CCF9; height: 2px; opacity: .8; }
.divider.d-nivel { color: #C08A00; }
.divider.d-nivel::after { background: #F8C045; height: 2px; opacity: .8; }
.divider.d-exc { color: var(--red); }
.divider.d-exc::after { background: var(--red); height: 2px; opacity: .35; }
/* Bloques de "por nivel": dorado 2024 */
.block-title.nivel {
  color: #5C4300;
  background: #F8C045;
  border-left: 3px solid #D99A00;
}
/* Prendas de niña (falda, jumper, suéter de botones, cuello olán): rosa 2024 */
.block-title.rosa {
  color: #6E1F78;
  background: #F5B8FB;
  border-left: 3px solid #C85AD6;
}
/* Formato de impresión: A4 horizontal (pedido de Daniel 2026-07-23) */
@page { size: A4 landscape; margin: 0; }
.page { width: 297mm; min-height: 210mm; }
@media print {
  /* alto libre al imprimir: evita que el redondeo de 210mm derrame
     una segunda página casi vacía por hoja */
  /* zoom 0.88: da aire vertical para que las hojas densas (faldas,
     pantalones, pants 2pz) quepan en un solo A4; el ancho se compensa */
  .page { min-height: 0; height: auto; zoom: 0.88; width: calc(297mm / 0.88); }
}
"""

# claves en forma normalizada (sin acentos, minúsculas) — se buscan con nrm()
DIV_CLASS = {
    "excepciones activas": "d-exc",
    "precios generales": "d-general",
    "liso · punto · algodon (generico)": "d-general",
    "deportivo por nivel": "d-nivel",
    "deportiva por nivel": "d-nivel",
    "oficial por nivel": "d-nivel",
    "oficial por escuela": "d-nivel",
    "en tiempo de oferta": "d-nivel",
    "faldas oficiales por escuela": "d-nivel",
}


# ── Datos ────────────────────────────────────────────────────────────────────
def cargar_env():
    env = HERE.parent / "pos_uniformes" / "pos_uniformes.env"
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


CACHE = HERE / "tarifarios_cache_filas.json"


def cargar_filas():
    """Lee las variantes de la DB; si la DB no responde, cae al cache local."""
    import json

    try:
        import psycopg

        cargar_env()
        conn = psycopg.connect(
            host=os.environ["POS_UNIFORMES_DB_HOST"],
            port=int(os.environ.get("POS_UNIFORMES_DB_PORT", "5432")),
            dbname=os.environ.get("POS_UNIFORMES_DB_NAME", "pos_uniformes"),
            user=os.environ.get("POS_UNIFORMES_DB_USER", "postgres"),
            password=os.environ.get("POS_UNIFORMES_DB_PASSWORD", ""),
            connect_timeout=10,
        )
        cur = conn.cursor()
        cur.execute(
            """
            select p.nombre, coalesce(e.nombre,''), coalesce(n.nombre,''),
                   v.talla, v.precio_venta
            from variante v
            join producto p on p.id = v.producto_id
            left join escuela e on e.id = p.escuela_id
            left join nivel_educativo n on n.id = p.nivel_educativo_id
            where v.activo and p.activo
            """
        )
        filas = [(p, e, n, t, float(pr)) for p, e, n, t, pr in cur.fetchall()]
        conn.close()
        CACHE.write_text(json.dumps(filas), encoding="utf-8")
        return filas
    except Exception as exc:
        if CACHE.exists():
            print(f"AVISO: DB inaccesible ({exc}); usando cache local {CACHE.name}")
            return [tuple(f) for f in json.loads(CACHE.read_text(encoding="utf-8"))]
        raise


def nrm(s):
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()


# ── Tallas ───────────────────────────────────────────────────────────────────
_ESPECIALES = {"0-0": 0.1, "0-2": 0.2, "3-5": 3.5, "6-8": 6.8, "9-12": 9.5, "13-18": 13.5}
_LETRAS = {"CH": 100, "CH-MD": 101, "MD": 102, "M": 102.5, "G": 103.5, "GD": 104,
           "GD-EXG": 105, "EXG": 106, "XL": 107, "XXL": 108, "DAMA": 110,
           "UNI": 111, "UNITALLA": 111, "ESP": 112, "NT": 113}


def talla_norm(t):
    t = t.strip().upper()
    return "UNI" if t == "UNITALLA" else t


def talla_key(t):
    t = talla_norm(t)
    if t in _ESPECIALES:
        return _ESPECIALES[t]
    if t in _LETRAS:
        return _LETRAS[t]
    try:
        return float(t)
    except ValueError:
        return 120


def fmt_precio(p):
    return f"${p:,.0f}" if float(p) == int(p) else f"${p:,.2f}"


# ── Escaleras ────────────────────────────────────────────────────────────────
def escalera(filas):
    """filas: [(prod, esc, talla, precio)] -> (rows_principal, excepciones)

    Escalera principal = precio modal por talla. En empate gana el precio que
    tenga producto genérico (sin escuela) — la escuela es la excepción — y si
    tampoco eso desempata, el mayor.
    excepciones = {etiqueta: [(talla, precio)]} para lo que se desvía del modal.
    """
    por_talla = defaultdict(Counter)
    generico = defaultdict(set)  # talla -> precios respaldados por producto sin escuela
    for prod, esc, talla, precio in filas:
        t, p = talla_norm(talla), float(precio)
        por_talla[t][p] += 1
        if not esc:
            generico[t].add(p)

    modal = {}
    for t, cnt in por_talla.items():
        top = max(cnt.values())
        candidatos = [p for p, c in cnt.items() if c == top]
        con_gen = [p for p in candidatos if p in generico[t]]
        modal[t] = max(con_gen) if con_gen else max(candidatos)

    grupos = defaultdict(list)  # precio -> [tallas]
    for t in sorted(modal, key=talla_key):
        grupos[modal[t]].append(t)
    rows = [[", ".join(ts), fmt_precio(p)]
            for p, ts in sorted(grupos.items(), key=lambda kv: talla_key(kv[1][0]))]

    exc = defaultdict(list)
    for prod, esc, talla, precio in filas:
        t = talla_norm(talla)
        if float(precio) != modal[t]:
            etiqueta = esc or prod.split("|")[0].strip()
            exc[etiqueta].append((t, float(precio)))
    return rows, exc


def bloque(titulo, filas, headers=("Tallas", "Precio")):
    """-> (block_data | None, excepciones)  block_data = (titulo, headers, rows)"""
    if not filas:
        return None, {}
    rows, exc = escalera(filas)
    return (titulo, list(headers), rows), exc


def bloques_excepciones(exc_por_familia):
    """{familia: {etiqueta: [(talla, precio)]}} -> [block_data]"""
    bloques = []
    for familia, excs in exc_por_familia.items():
        if not excs:
            continue
        rows = []
        for etiqueta in sorted(excs):
            grupos = defaultdict(list)
            for t, p in sorted(set(excs[etiqueta]), key=lambda tp: talla_key(tp[0])):
                grupos[p].append(t)
            for p, ts in sorted(grupos.items(), key=lambda kv: talla_key(kv[1][0])):
                rows.append([etiqueta, ", ".join(ts), fmt_precio(p)])
        if rows:
            bloques.append((familia, ["Escuela / Producto", "Tallas", "Precio"], rows))
    return bloques


# ── Clasificación de filas DB ────────────────────────────────────────────────
class Filas:
    def __init__(self, filas):
        self.filas = list(filas)

    def sel(self, fn):
        return [(p, e, t, pr) for p, e, n, t, pr in self.filas
                if fn(nrm(p.split("|")[0]), nrm(p), e, n)]


def _seccion(F, defs, excs, bloques):
    """defs: [(titulo, matcher)] — acumula bloques presentes y sus excepciones."""
    for titulo, fn in defs:
        b, e = bloque(titulo, F.sel(fn))
        if b:
            bloques.append(b)
            excs[titulo] = e


def paginas(F):
    """-> [(name, category, title, items)]
    item: ("divider", label) | ("grid", cols, [block_data]) | ("grid_exc", cols, [block_data])
    """
    P = []

    def cerrar(items, excs, cols=3):
        """Las excepciones van ARRIBA de la página (pedido de Daniel 2026-07-22)."""
        ex = bloques_excepciones(excs)
        if ex:
            # separador para la sección regular, salvo que ya empiece con uno propio
            if items and items[0][0] != "divider":
                items.insert(0, ("divider", "Precios generales"))
            items.insert(0, ("grid_exc", min(cols, len(ex)), ex))
            items.insert(0, ("divider", "Excepciones activas"))

    # Playeras deportivas
    # Motolinea es excepción total ($235 parejo): fuera de la escalera base
    # para que sus tallas únicas (p.ej. la 2) no contaminen los renglones
    bloques, excs = [], {}
    _seccion(F, [
        (nivel, (lambda b_, p, e_, n, _n=nivel: n == _n and
                 (b_.startswith("playera deportiva") or
                  (b_.startswith("playera") and "deportivo" in p))
                 and "motolinea" not in b_))
        for nivel in ("Preescolar", "Primaria", "Secundaria", "Bachillerato")
    ], excs, bloques)
    moto = F.sel(lambda b_, p, e_, n: b_.startswith("playera") and "deportiv" in p
                 and "motolinea" in b_)
    if moto:
        excs.setdefault("Primaria", {})["Colegio Motolinea"] = [
            (t, float(pr)) for _, _, t, pr in moto]
    bloques = [(t, h, r, "nivel") for t, h, r in bloques]
    items = [("divider", "Deportivo por nivel"), ("grid", 4, bloques)]
    cerrar(items, excs)
    P.append(("Playeras", "Ropa Deportiva", "Playeras Deportivas", items))

    # Suéteres
    bloques, excs = [], {}
    _seccion(F, [
        ("Básico", lambda b_, p, e_, n: b_.startswith("sueter claudia")),
        # "Oferta Ad hoc" (UNI $199) excluida del tarifario a pedido de Daniel
        # (2026-07-23); sigue activa y vendible en el POS.
    ], excs, bloques)
    bloques_niv = []
    _seccion(F, [
        (f"Oficial {nivel}", (lambda b_, p, e_, n, _n=nivel: n == _n and b_.startswith("sueter")
                              and "oficial" in p and "claudia" not in b_))
        for nivel in ("Preescolar", "Primaria", "Secundaria", "Bachillerato")
    ], excs, bloques_niv)
    bloques_niv = [(t, h, r, "nivel") for t, h, r in bloques_niv]
    items = [("divider", "Precios generales"), ("grid", 3, bloques),
             ("divider", "Oficial por nivel"), ("grid", 4, bloques_niv)]
    cerrar(items, excs)
    P.append(("Sueteres", "Suéteres", "Suéteres", items))

    # Chamarras
    bloques, excs = [], {}
    _seccion(F, [
        ("Básica Liso", lambda b_, p, e_, n: b_.startswith("chamarra liso")),
        ("Básica Punto", lambda b_, p, e_, n: b_.startswith("chamarra punto")),
    ], excs, bloques)
    bloques_niv = []
    _seccion(F, [
        (f"Deportiva · {nivel}", (lambda b_, p, e_, n, _n=nivel: n == _n and
                                  b_.startswith("chamarra") and "deportivo" in p))
        for nivel in ("Preescolar", "Primaria", "Secundaria", "Bachillerato")
    ], excs, bloques_niv)
    bloques_niv = [(t, h, r, "nivel") for t, h, r in bloques_niv]
    items = [("divider", "Precios generales"), ("grid", 2, bloques),
             ("divider", "Deportiva por nivel"), ("grid", 4, bloques_niv)]
    cerrar(items, excs)
    P.append(("Chamarras", "Chamarras", "Chamarras", items))

    # Chalecos
    bloques, excs = [], {}
    _seccion(F, [
        ("Básico · sin escuela", lambda b_, p, e_, n: b_.startswith("chaleco claudia")
            or (b_.startswith("chaleco") and "basico" in p)),
    ], excs, bloques)
    bloques_of = []
    _seccion(F, [
        (f"Oficial · {nivel}", (lambda b_, p, e_, n, _n=nivel: n == _n and
                                b_.startswith("chaleco") and "oficial" in p))
        for nivel in ("Preescolar", "Primaria", "Secundaria", "Bachillerato")
    ], excs, bloques_of)
    bloques_of = [(t, h, r, "nivel") for t, h, r in bloques_of]
    items = [("divider", "Precios generales"), ("grid", 3, bloques),
             ("divider", "Oficial por nivel"), ("grid", 3, bloques_of)]
    cerrar(items, excs, cols=2)
    P.append(("Chalecos", "Chalecos", "Chalecos", items))

    # Camisas (manga corta + polo; cuello olán = oficial preescolar)
    bloques, excs = [], {}
    _seccion(F, [
        ("Manga Corta Blanca", lambda b_, p, e_, n: b_ == "camisa manga corta blanca"),
        ("Prowear Manga Corta", lambda b_, p, e_, n: b_.startswith("camisa prowear")),
        ("Playera Polo Blanca", lambda b_, p, e_, n: b_ == "playera polo blanca"),
    ], excs, bloques)
    bloques_niv = []
    _seccion(F, [
        ("Oficial · Preescolar (Cuello Olán)",
         lambda b_, p, e_, n: b_.startswith("camisa cuello olan")),
    ], excs, bloques_niv)
    bloques_niv = [(t, h, r, "nivel") for t, h, r in bloques_niv]
    items = [("divider", "Precios generales"), ("grid", 3, bloques),
             ("divider", "Oficial por nivel"), ("grid", 3, bloques_niv)]
    cerrar(items, excs)
    P.append(("Camisas", "Camisas", "Camisas y Playeras Manga Corta", items))

    # Camisas Manga Larga (H/M + oficiales por nivel)
    bloques, excs = [], {}
    _seccion(F, [
        ("Manga Larga H Blanca", lambda b_, p, e_, n: b_ == "camisa manga larga h blanca"),
        ("Manga Larga M Blanca", lambda b_, p, e_, n: b_ == "camisa manga larga m blanca"),
    ], excs, bloques)
    # Francisco Villa es la excepción de la línea oficial (estándar $265):
    # se muestra su escalera completa en rojo
    fv = F.sel(lambda b_, p, e_, n: b_.startswith("camisa") and "oficial" in p
               and "francisco villa" in b_)
    if fv:
        excs["Oficiales por escuela"] = {"Francisco Villa": [(t, float(pr)) for _, _, t, pr in fv]}
    bloques_niv = []
    _seccion(F, [
        (f"Oficial · {nivel}", (lambda b_, p, e_, n, _n=nivel: n == _n and
                                b_.startswith("camisa") and "oficial" in p and
                                "cuello olan" not in b_ and "francisco villa" not in b_))
        for nivel in ("Preescolar", "Primaria", "Secundaria", "Bachillerato")
    ], {}, bloques_niv)
    bloques_niv = [(t, h, r, "nivel") for t, h, r in bloques_niv]
    items = [("divider", "Precios generales"), ("grid", 3, bloques),
             ("divider", "Oficial por nivel"), ("grid", 3, bloques_niv)]
    cerrar(items, excs)
    P.append(("Camisas_Manga_Larga", "Camisas", "Camisas Manga Larga", items))

    # Pants 2pz / 3pz
    # Colores de Pants 2pz Liso con oferta activa (tallas infantiles): se muestran
    # en su propia tabla "En tiempo de oferta" en lugar de salir como excepciones.
    PROMO_LISO_2PZ = ("azul marino", "azul rey", "rojo", "verde", "vino")

    def _es_promo_liso(b_):
        return b_.startswith("pants 2pz liso") and any(c in b_ for c in PROMO_LISO_2PZ)

    for pz, nombre_pag, titulo_pag in (("2", "Pants_2pz", "Pants 2 Piezas"),
                                       ("3", "Pants_3pz", "Pants 3 Piezas")):
        pref = f"pants {pz}pz "
        bloques, excs = [], {}
        _seccion(F, [
            ("Liso", lambda b_, p, e_, n, _p=pref, _pz=pz: b_.startswith(_p + "liso")
                and "deportivo" not in p and not (_pz == "2" and _es_promo_liso(b_))),
            ("Punto", lambda b_, p, e_, n, _p=pref: b_.startswith(_p + "punto")
                and "deportivo" not in p),
            ("Algodón", lambda b_, p, e_, n, _p=pref: b_.startswith(_p + "algodon")),
        ], excs, bloques)
        items = []
        if bloques:
            items += [("divider", "Liso · Punto · Algodón (genérico)"), ("grid", 3, bloques)]

        # Tabla "En tiempo de oferta" eliminada del tarifario a pedido de Daniel
        # (2026-07-23). Los colores promo siguen excluidos de la escalera Liso para
        # no salir como excepciones; sus precios en DB no se tocan. Para revivir la
        # tabla, cambiar False por (pz == "2").
        if False:
            promo = [r for r in F.sel(lambda b_, p, e_, n: _es_promo_liso(b_))
                     if r[2].strip().isdigit() and int(r[2]) <= 16]
            if promo:
                def rango(tallas_str):
                    """'2, 4, 6, 8, 10, 12' -> '2 – 12' cuando son pares consecutivos."""
                    ts = [t.strip() for t in tallas_str.split(",")]
                    if len(ts) >= 3 and all(t.isdigit() for t in ts):
                        nums = [int(t) for t in ts]
                        if nums == list(range(nums[0], nums[-1] + 1, 2)):
                            return f"{nums[0]} – {nums[-1]}"
                    return tallas_str

                por_color = defaultdict(list)
                for prod, esc, t, pr in promo:
                    color = prod.split("|")[0].strip()[len("Pants 2pz Liso "):]
                    por_color[color].append((prod, esc, t, pr))
                # agrupar colores que comparten la misma escalera -> un renglón por grupo
                por_escalera = defaultdict(list)
                for color in sorted(por_color):
                    r, _ = escalera(por_color[color])
                    por_escalera[tuple(map(tuple, r))].append(color)
                bloques_of = []
                for esc_r, colores in por_escalera.items():
                    headers = ["Colores"] + [rango(tallas) for tallas, _ in esc_r]
                    fila = [" · ".join(colores)] + [precio for _, precio in esc_r]
                    bloques_of.append(("Pants 2pz Liso · Oferta", headers, [fila]))
                items.append(("divider", "En tiempo de oferta"))
                items.append(("grid", 2, bloques_of))

        bloques2, excs2 = [], {}
        _seccion(F, [
            (f"Deportivo · {nivel}",
             (lambda b_, p, e_, n, _pz=pz, _n=nivel: n == _n and
              b_.startswith(f"pants {_pz}pz") and "deportivo" in p and
              "liso" not in b_ and "punto" not in b_ and "algodon" not in b_))
            for nivel in ("Preescolar", "Primaria", "Secundaria", "Bachillerato")
        ], excs2, bloques2)
        bloques2 = [(t, h, r, "nivel") for t, h, r in bloques2]
        items += [("divider", "Deportivo por nivel"), ("grid", 4, bloques2)]
        excs.update(excs2)
        cerrar(items, excs)
        P.append((nombre_pag, "Pants", titulo_pag, items))

    # Pants suelto
    bloques, excs = [], {}
    _seccion(F, [
        ("Liso", lambda b_, p, e_, n: b_.startswith("pants suelto liso")),
        ("Punto", lambda b_, p, e_, n: b_.startswith("pants suelto punto")),
    ], excs, bloques)
    # Deportivo condensado por nivel: el precio depende del nivel, no de la escuela.
    # Si una escuela se desvía de su nivel, cae automáticamente a Excepciones.
    rows_nivel = []
    for nivel in ("Preescolar", "Primaria", "Secundaria", "Bachillerato"):
        filas_n = [(pn, en, t, pr) for pn, en, nn, t, pr in F.filas
                   if nn == nivel and nrm(pn.split("|")[0]).startswith("pants suelto")
                   and "deportivo" in nrm(pn)]
        if not filas_n:
            continue
        r, ex = escalera(filas_n)
        for tallas, precio in r:
            rows_nivel.append([nivel, tallas, precio])
        if ex:
            excs[f"Deportivo · {nivel}"] = ex
    items = [("divider", "Precios generales"), ("grid", 3, bloques)]
    if rows_nivel:
        items += [("divider", "Deportivo por nivel"),
                  ("grid", 3, [("Deportivo por nivel", ["Nivel", "Tallas", "Precio"],
                                rows_nivel, "nivel")])]
    cerrar(items, excs)
    P.append(("Pants_Suelto", "Pants", "Pants Suelto", items))

    # Pantalones
    bloques, excs = [], {}
    _seccion(F, [
        ("Vestir · colores estándar", lambda b_, p, e_, n: b_.startswith("pantalon vestir")
            and "gris claro" not in b_ and "gris obscuro" not in b_
            and "pata de gallo" not in b_ and "mujer" not in b_),
        ("Vestir Gris · Claro y Obscuro", lambda b_, p, e_, n:
            b_.startswith("pantalon vestir gris claro") or b_.startswith("pantalon vestir gris obscuro")),
        ("Vestir Mujer", lambda b_, p, e_, n: b_.startswith("pantalon vestir mujer")),
        ("Pata de Gallo", lambda b_, p, e_, n: b_.startswith("pantalon vestir pata de gallo")),
        ("Gales · Azul, Rojo, Verde", lambda b_, p, e_, n: b_.startswith("pantalon gales")),
        ("Escocés", lambda b_, p, e_, n: b_.startswith("pantalon escoces")),
        # Gabardina Negro excluido del tarifario a pedido de Daniel (2026-07-22);
        # sigue activo y vendible en el POS.
    ], excs, bloques)
    items = [("grid", 3, bloques)]
    cerrar(items, excs)
    P.append(("Pantalones", "Pantalones", "Pantalones", items))

    # Faldas
    bloques, excs = [], {}
    # Orden pedido por Daniel (2026-07-23): jumper, cuatro tablas, gales,
    # escocés y al final las grises
    _seccion(F, [
        ("Jumper", lambda b_, p, e_, n: b_.startswith("jumper")),
        # Fusionadas 2026-07-22: comparten escalera exacta
        ("Cuatro Tablas · Tableada · Escolar A.M. · Vino", lambda b_, p, e_, n:
            b_.startswith("falda cuatro tablas") or b_.startswith("falda tableada")
            or b_ == "falda escolar azul marino" or b_ == "falda vino"),
        ("Gales · Azul, Rojo, Verde", lambda b_, p, e_, n: b_.startswith("falda gales")),
        ("Escocés", lambda b_, p, e_, n: b_ == "falda escoces"),
        ("Gris · Claro y Obscuro", lambda b_, p, e_, n: b_.startswith("falda gris")),
        # Pgallo Café excluida del tarifario a pedido de Daniel (2026-07-22);
        # sigue activa y vendible en el POS (precios = escalera Motolinea).
    ], excs, bloques)
    # Oficial por escuela: no hay producto "base" — cada escuela tiene su propia
    # escalera, así que se muestra una tabla por escuela en vez de modal+excepciones.
    bloque_oficial = None
    filas_of = [(pn, en, t, pr) for pn, en, nn, t, pr in F.filas
                if nrm(pn.split("|")[0]).startswith("falda")
                and ("oficial" in nrm(pn) or "margarita" in nrm(pn.split("|")[0]))]
    if filas_of:
        # Conalep y SABES comparten precios desde 2026-07-22 -> una sola tabla
        fusion = {"Conalep": "Conalep · SABES", "SABES": "Conalep · SABES"}
        por_esc = defaultdict(list)
        for pn, en, t, pr in filas_of:
            etiqueta = en or pn.split("|")[0].strip()
            por_esc[fusion.get(etiqueta, etiqueta)].append((pn, en, t, pr))
        bloques_of = []
        for esc_n in sorted(por_esc):
            r, _ = escalera(por_esc[esc_n])
            bloques_of.append((esc_n, ["Tallas", "Precio"], [[tallas, precio] for tallas, precio in r]))
        bloque_oficial = bloques_of
    items = [("divider", "Precios generales"), ("grid", 4, bloques)]
    if bloque_oficial:
        items.append(("divider", "Faldas oficiales por escuela"))
        items.append(("grid_exc", min(4, len(bloque_oficial)), bloque_oficial))
    cerrar(items, excs)
    P.append(("Faldas", "Faldas", "Faldas · Jumper", items))

    # Accesorios · Polo (incluye Malla y Bata desde 2026-07-23; Jumper vive en Faldas)
    rows, excs = [], {}
    for titulo, fn in [
        ("Calceta Escolar", lambda b_, p, e_, n: b_.startswith("calceta escolar")),
        ("Guante Escolta", lambda b_, p, e_, n: b_.startswith("guante escolta")),
        ("Corbata", lambda b_, p, e_, n: b_.startswith("corbata")),
        ("Corbatín", lambda b_, p, e_, n: b_.startswith("corbatin")),
        ("Moño", lambda b_, p, e_, n: b_.startswith("mono ")),
        ("Boina Escolta", lambda b_, p, e_, n: b_.startswith("boina escolta")),
    ]:
        filas = F.sel(fn)
        if filas:
            r, e = escalera(filas)
            rows.append([titulo, " / ".join(pr for _, pr in r)])
            excs[titulo] = e
    bloques = [("Accesorios", ["Pieza", "Precio"], rows)]
    b, e = bloque("Malla Escolar", F.sel(lambda b_, p, e_, n: b_.startswith("malla escolar")))
    if b:
        bloques.append(b)
        excs["Malla Escolar"] = e
    rows_bata = []
    for titulo, fn in [
        ("Infantil", lambda b_, p, e_, n: b_.startswith("bata infantil")),
        ("Manga Corta", lambda b_, p, e_, n: b_.startswith("bata manga corta")),
        ("Manga Larga", lambda b_, p, e_, n: b_.startswith("bata manga larga")),
    ]:
        filas = F.sel(fn)
        if filas:
            r, e = escalera(filas)
            for tallas, precio in r:
                rows_bata.append([titulo, tallas, precio])
            excs[f"Bata {titulo}"] = e
    if rows_bata:
        bloques.append(("Bata", ["Tipo", "Tallas", "Precio"], rows_bata))
    items = [("divider", "Precios generales"), ("grid", 3, bloques)]
    cerrar(items, excs, cols=2)
    P.append(("Accesorios_Polo", "Accesorios", "Accesorios · Malla · Bata", items))

    # Orden de hojas definido por Daniel (2026-07-23)
    ORDEN = ["Pants_3pz", "Pants_2pz", "Chamarras", "Pants_Suelto", "Playeras",
             "Sueteres", "Chalecos", "Camisas", "Camisas_Manga_Larga",
             "Pantalones", "Faldas",
             "Accesorios_Polo"]
    P.sort(key=lambda pg: ORDEN.index(pg[0]) if pg[0] in ORDEN else 99)
    return P


# ── Render HTML ──────────────────────────────────────────────────────────────
def html_block(b, exc=False):
    t, h, r = b[0], b[1], b[2]
    html = base.block(t, h, r, exc=exc)
    if len(b) > 3 and b[3] in ("nivel", "rosa"):
        html = html.replace('class="block-title "', f'class="block-title {b[3]}"', 1)
    return html


def html_page(category, title, items):
    cuerpo = ""
    for item in items:
        if item[0] == "divider":
            cls = DIV_CLASS.get(nrm(item[1]), "")
            cuerpo += f'<div class="divider {cls}">{item[1]}</div>' if cls else base.divider(item[1])
        else:
            kind, cols, blocks = item
            exc = kind == "grid_exc"
            cuerpo += base.grid(cols, *[html_block(b, exc=exc) for b in blocks])
    return f"""
<div class="page">
  <div class="page-header">
    <div class="header-left">
      <div class="header-category">{DOC_NOMBRE} · {category}</div>
      <div class="header-title">{title}</div>
    </div>
    <div class="header-right">
      <div class="header-date">Actualizado: {FECHA}</div>
    </div>
  </div>
  {cuerpo}
</div>"""


def generar_html(P):
    OUT_HTML.mkdir(exist_ok=True)
    todas = "\n".join(html_page(cat, tit, items) for _, cat, tit, items in P)
    html = base.HTML_WRAPPER.format(title="Tarifario General 2026", css=base.CSS + CSS_EXTRA, body=todas)
    out = OUT_HTML / "Tarifario_Completo_2026.html"
    out.write_text(html, encoding="utf-8")
    print(f"Generado: {out}")

    for name, cat, tit, items in P:
        html = base.HTML_WRAPPER.format(
            title=f"Tarifario {name.replace('_', ' ')} 2026",
            css=base.CSS + CSS_EXTRA, body=html_page(cat, tit, items))
        p = OUT_HTML / f"Tarifario_{name}_2026.html"
        p.write_text(html, encoding="utf-8")
        print(f"  + {p.name}")


# ── Editor drag & drop ───────────────────────────────────────────────────────
EDITOR_CSS = """
body { padding-top: 64px; }
.toolbar {
  position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
  background: #1B3557; color: #fff; padding: 10px 18px;
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  box-shadow: 0 2px 12px rgba(0,0,0,.25); font-size: 13px;
}
.toolbar b { margin-right: 6px; }
.toolbar button {
  background: #2C4E80; color: #fff; border: 1px solid #4A6EA5;
  border-radius: 6px; padding: 6px 12px; font: inherit; cursor: pointer;
}
.toolbar button:hover { background: #3A5E95; }
.toolbar .status { margin-left: auto; opacity: .85; font-size: 12px; }
.block { cursor: grab; position: relative; }
.block.dragging { opacity: .35; outline: 2px dashed #C96030; }
.divider { cursor: grab; position: relative; }
.divider.dragging { opacity: .35; outline: 2px dashed #C96030; }
.div-del {
  background: #C92020; color: #fff; border: none; border-radius: 50%;
  width: 16px; height: 16px; line-height: 14px; font-size: 10px;
  cursor: pointer; opacity: 0; transition: opacity .15s; padding: 0;
  margin-left: 8px; vertical-align: middle;
}
.divider:hover .div-del { opacity: .9; }
.block.deleted-block { display: none; }
.block-del {
  position: absolute; top: 2px; right: 2px; z-index: 6;
  background: #C92020; color: #fff; border: none; border-radius: 50%;
  width: 18px; height: 18px; line-height: 16px; font-size: 11px;
  cursor: pointer; opacity: 0; transition: opacity .15s; padding: 0;
}
.block:hover .block-del { opacity: .9; }
.page { position: relative; }
.page-controls {
  position: absolute; top: 8px; right: 12px; display: flex; gap: 5px; z-index: 6;
}
.page-controls button {
  background: rgba(255,255,255,.15); color: #fff; border: 1px solid rgba(255,255,255,.4);
  border-radius: 6px; padding: 2px 9px; cursor: pointer; font-size: 12px;
}
.page-controls button:hover { background: rgba(255,255,255,.3); }
/* ── Panel de miniaturas ── */
#sidebar {
  position: fixed; top: 64px; left: 0; bottom: 0; width: 186px;
  overflow-y: auto; background: #14213A; padding: 12px 10px; z-index: 900;
}
body.with-sidebar { padding-left: 196px; }
.thumb {
  background: #fff; border-radius: 5px; margin-bottom: 4px; cursor: grab;
  overflow: hidden; border: 2px solid transparent;
  box-shadow: 0 1px 6px rgba(0,0,0,.35);
}
.thumb:hover { border-color: #C96030; }
.thumb.dragging { opacity: .35; border-color: #C96030; border-style: dashed; }
.thumb-canvas { width: 162px; height: 122px; overflow: hidden; pointer-events: none; }
.thumb-canvas .page {
  transform: scale(0.153); transform-origin: top left;
  margin: 0 !important; box-shadow: none !important; width: 11in;
}
.thumb-num {
  position: absolute; margin: 4px 0 0 4px; background: #1B3557; color: #fff;
  font-size: 10px; border-radius: 8px; padding: 1px 7px; opacity: .9; position: relative;
  float: left;
}
.thumb-label {
  font-size: 10px; color: #C7D4E8; margin: 2px 2px 12px 4px; line-height: 1.25;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.grid { min-height: 46px; border-radius: 6px; }
.grid.dragover { outline: 2px dashed #2C4E80; outline-offset: 3px; background: #EBF2FF44; }
.grid-cols-btn {
  position: absolute; top: -9px; right: -6px; z-index: 5;
  background: #C96030; color: #fff; border: none; border-radius: 10px;
  font-size: 10px; padding: 2px 8px; cursor: pointer; opacity: .85;
}
.grid-wrap { position: relative; }
@media print {
  body, body.with-sidebar { padding-top: 0; padding-left: 0; }
  .toolbar, .grid-cols-btn, .block-del, .page-controls, #sidebar, .div-del { display: none !important; }
  .block, .divider { cursor: default; }
}
"""

EDITOR_JS = r"""
const LS_KEY = 'tarifario_layout_v1';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

function setStatus(msg) {
  $('#status').textContent = msg;
  clearTimeout(setStatus._t);
  setStatus._t = setTimeout(() => $('#status').textContent = '', 4000);
}

function assignKeys() {
  // claves basadas en el NOMBRE de la hoja (no en su posición): así las
  // disposiciones guardadas sobreviven cuando se agregan o reordenan hojas
  $$('.page').forEach((page, pi) => {
    const tit = page.querySelector('.header-title');
    const pk = (tit ? tit.textContent : 'pag' + pi).trim();
    page.dataset.pageKey = pk;
    const counts = {};
    page.querySelectorAll('.block').forEach(b => {
      const tEl = b.querySelector('.block-title');
      const title = (tEl ? tEl.textContent : '').trim().toLowerCase();
      const exc = tEl && tEl.classList.contains('exc') ? '1' : '0';
      const k0 = pk + '::' + title + '::' + exc;
      counts[k0] = (counts[k0] || 0) + 1;
      b.dataset.key = k0 + '::' + counts[k0];
      b.setAttribute('draggable', 'true');
    });
    page.querySelectorAll('.grid').forEach((g, gi) => { g.dataset.gridId = pk + '-' + gi; });
    page.querySelectorAll(':scope > .divider').forEach(d => {
      const txt = d.textContent.trim();
      const k0 = pk + '::div::' + txt.toLowerCase();
      counts[k0] = (counts[k0] || 0) + 1;
      d.dataset.key = k0 + '::' + counts[k0];
      d.dataset.text = txt;
    });
  });
}

// ── Marcadores (separadores) ──
const deletedDivKeys = new Set();
function prepDivider(d) {
  d.setAttribute('draggable', 'true');
  d.innerHTML = '';
  d.appendChild(document.createTextNode(d.dataset.text));
  const del = document.createElement('button');
  del.className = 'div-del';
  del.type = 'button';
  del.textContent = '×';
  del.title = 'Quitar este marcador';
  del.onclick = e => {
    e.stopPropagation();
    deletedDivKeys.add(d.dataset.key);
    d.remove();
    saveLayout(true);
    setStatus('Marcador eliminado');
  };
  d.appendChild(del);
  d.ondblclick = () => {
    const t = prompt('Texto del marcador:', d.dataset.text);
    if (t && t.trim()) {
      d.dataset.text = t.trim();
      prepDivider(d);
      saveLayout(true);
    }
  };
  d.title = 'Arrastra para mover · doble clic para renombrar';
}

function makeDivider(text, key) {
  const d = document.createElement('div');
  d.className = 'divider';
  d.dataset.key = key;
  d.dataset.text = text;
  prepDivider(d);
  return d;
}

function paginaVisible() {
  const centro = window.innerHeight / 2;
  for (const p of $$('#pages > .page')) {
    const r = p.getBoundingClientRect();
    if (r.top <= centro && r.bottom >= centro) return p;
  }
  return $('#pages > .page');
}

function agregarMarcador() {
  const t = prompt('Texto del nuevo marcador:', '');
  if (!t || !t.trim()) return;
  const page = paginaVisible();
  const d = makeDivider(t.trim(), 'custom-' + Math.random().toString(36).slice(2, 9));
  const header = page.querySelector('.page-header');
  header.after(d);
  d.scrollIntoView({ behavior: 'smooth', block: 'center' });
  saveLayout(true);
  setStatus('Marcador agregado en "' + page.dataset.pageKey + '" — arrástralo a su lugar');
}

// ── Eliminar / restaurar tablas ──
function addDeleteButtons() {
  $$('.block').forEach(b => {
    const btn = document.createElement('button');
    btn.className = 'block-del';
    btn.type = 'button';
    btn.textContent = '×';
    btn.title = 'Quitar esta tabla del tarifario';
    btn.onclick = e => {
      e.stopPropagation();
      b.classList.add('deleted-block');
      saveLayout(true);
      updateTrash();
      setStatus('Tabla eliminada — usa 🗑 para restaurar');
    };
    b.appendChild(btn);
  });
}

function updateTrash() {
  const n = $$('.block.deleted-block').length;
  const btn = $('#btn-trash');
  btn.style.display = n ? '' : 'none';
  btn.textContent = '🗑 Restaurar tablas (' + n + ')';
}

function restoreDeleted() {
  $$('.block.deleted-block').forEach(b => b.classList.remove('deleted-block'));
  saveLayout(true);
  updateTrash();
  setStatus('Tablas restauradas');
}

// ── Reordenar hojas ──
function addPageControls() {
  $$('.page').forEach(page => {
    const ctl = document.createElement('div');
    ctl.className = 'page-controls';
    const up = document.createElement('button');
    up.type = 'button'; up.textContent = '▲'; up.title = 'Subir esta hoja';
    const down = document.createElement('button');
    down.type = 'button'; down.textContent = '▼'; down.title = 'Bajar esta hoja';
    up.onclick = () => movePage(page, -1);
    down.onclick = () => movePage(page, 1);
    ctl.appendChild(up); ctl.appendChild(down);
    page.appendChild(ctl);
  });
}

function movePage(page, dir) {
  const cont = page.parentNode;
  const pages = [...cont.querySelectorAll(':scope > .page')];
  const i = pages.indexOf(page);
  const j = i + dir;
  if (j < 0 || j >= pages.length) return;
  if (dir < 0) cont.insertBefore(page, pages[j]);
  else cont.insertBefore(pages[j], page);
  page.scrollIntoView({ behavior: 'smooth', block: 'start' });
  saveLayout(true);
  setStatus('Hoja "' + page.dataset.pageKey + '" movida');
}

// ── Panel de miniaturas ──
function buildSidebar() {
  const sb = $('#sidebar');
  if (!sb) return;
  sb.innerHTML = '';
  $$('#pages > .page').forEach((p, i) => {
    const th = document.createElement('div');
    th.className = 'thumb';
    th.draggable = true;
    th.dataset.pageKey = p.dataset.pageKey;
    th.title = p.dataset.pageKey + ' — arrastra para reordenar, clic para ir';
    const cv = document.createElement('div');
    cv.className = 'thumb-canvas';
    const clone = p.cloneNode(true);
    clone.querySelectorAll('.page-controls, .block-del, .grid-cols-btn, .block.deleted-block')
      .forEach(x => x.remove());
    cv.appendChild(clone);
    th.appendChild(cv);
    th.onclick = () => p.scrollIntoView({ behavior: 'smooth', block: 'start' });
    sb.appendChild(th);
    const lb = document.createElement('div');
    lb.className = 'thumb-label';
    lb.textContent = (i + 1) + '. ' + p.dataset.pageKey;
    sb.appendChild(lb);
  });
}

let thumbDragged = null;
function wireSidebar() {
  const sb = $('#sidebar');
  sb.addEventListener('dragstart', e => {
    const th = e.target.closest('.thumb');
    if (!th) return;
    thumbDragged = th;
    e.dataTransfer.effectAllowed = 'move';
    setTimeout(() => th.classList.add('dragging'));
  });
  sb.addEventListener('dragover', e => {
    if (!thumbDragged) return;
    e.preventDefault();
    const th = e.target.closest('.thumb');
    if (!th || th === thumbDragged) return;
    const r = th.getBoundingClientRect();
    const antes = e.clientY < r.top + r.height / 2;
    const lbl = thumbDragged.nextElementSibling; // su etiqueta viaja con él
    if (antes) sb.insertBefore(thumbDragged, th);
    else sb.insertBefore(thumbDragged, th.nextElementSibling.nextSibling);
    if (lbl && lbl.classList.contains('thumb-label')) sb.insertBefore(lbl, thumbDragged.nextSibling);
  });
  sb.addEventListener('dragend', () => {
    if (!thumbDragged) return;
    thumbDragged.classList.remove('dragging');
    thumbDragged = null;
    // aplicar el orden de las miniaturas a las hojas reales
    const cont = $('#pages');
    const byKey = {};
    $$('#pages > .page').forEach(p => byKey[p.dataset.pageKey] = p);
    [...sb.querySelectorAll('.thumb')].forEach(th => {
      const p = byKey[th.dataset.pageKey];
      if (p) cont.appendChild(p);
    });
    saveLayout(true);
    buildSidebar();
    setStatus('Orden de hojas actualizado');
  });
}

function addColsButtons() {
  $$('.grid').forEach(g => {
    const wrap = document.createElement('div');
    wrap.className = 'grid-wrap';
    g.parentNode.insertBefore(wrap, g);
    wrap.appendChild(g);
    const btn = document.createElement('button');
    btn.className = 'grid-cols-btn';
    btn.type = 'button';
    const cols = () => parseInt(([...g.classList].find(c => c.startsWith('cols-')) || 'cols-3').slice(5));
    btn.textContent = '▤ ' + cols();
    btn.title = 'Cambiar número de columnas';
    btn.onclick = () => {
      const n = cols() % 4 + 1;
      g.classList.remove('cols-1', 'cols-2', 'cols-3', 'cols-4');
      g.classList.add('cols-' + n);
      btn.textContent = '▤ ' + n;
      saveLayout(true);
    };
    wrap.appendChild(btn);
  });
}

// ── Drag & drop ──
let dragged = null;       // tabla
let draggedDiv = null;    // marcador
document.addEventListener('dragstart', e => {
  const d = e.target.closest('.divider');
  if (d) {
    draggedDiv = d;
    e.dataTransfer.effectAllowed = 'move';
    setTimeout(() => d.classList.add('dragging'));
    return;
  }
  const b = e.target.closest('.block');
  if (!b) return;
  dragged = b;
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', b.dataset.key);
  setTimeout(() => b.classList.add('dragging'));
});
document.addEventListener('dragend', () => {
  if (dragged) dragged.classList.remove('dragging');
  if (draggedDiv) draggedDiv.classList.remove('dragging');
  dragged = draggedDiv = null;
  $$('.grid.dragover').forEach(g => g.classList.remove('dragover'));
  saveLayout(true);
});
document.addEventListener('dragover', e => {
  if (draggedDiv) {
    const page = e.target.closest('.page');
    if (!page) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    // insertar entre los hijos de la página (secciones y otros marcadores)
    const hijos = [...page.children].filter(el =>
      el !== draggedDiv && !el.classList.contains('page-header') &&
      !el.classList.contains('page-controls'));
    let destino = null;
    for (const el of hijos) {
      const r = el.getBoundingClientRect();
      if (e.clientY < r.top + r.height / 2) { destino = el; break; }
    }
    if (destino) { if (destino !== draggedDiv.nextSibling) page.insertBefore(draggedDiv, destino); }
    else {
      const ctl = page.querySelector(':scope > .page-controls');
      page.insertBefore(draggedDiv, ctl);
    }
    return;
  }
  if (!dragged) return;
  const g = e.target.closest('.grid');
  if (!g) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  $$('.grid.dragover').forEach(x => x !== g && x.classList.remove('dragover'));
  g.classList.add('dragover');
  const before = insertBefore(g, e.clientX, e.clientY);
  if (before) { if (before !== dragged) g.insertBefore(dragged, before); }
  else if (g.lastElementChild !== dragged) g.appendChild(dragged);
});
document.addEventListener('drop', e => {
  if ((dragged && e.target.closest('.grid')) || (draggedDiv && e.target.closest('.page')))
    e.preventDefault();
});

function insertBefore(grid, x, y) {
  for (const el of grid.querySelectorAll(':scope > .block:not(.dragging)')) {
    const r = el.getBoundingClientRect();
    if (y < r.top || (y <= r.bottom && x < r.left + r.width / 2)) return el;
  }
  return null;
}

// ── Persistencia ──
function layoutData() {
  return {
    grids: $$('.grid').map(g => ({
      id: g.dataset.gridId,
      cols: [...g.classList].find(c => c.startsWith('cols-')) || 'cols-3',
      blocks: [...g.querySelectorAll(':scope > .block')].map(b => b.dataset.key),
    })),
    deleted: $$('.block.deleted-block').map(b => b.dataset.key),
    pageOrder: $$('.page').map(p => p.dataset.pageKey),
    dividers: $$('#pages > .page').flatMap(p =>
      [...p.querySelectorAll(':scope > .divider')].map(d => {
        // ancla: el siguiente grid de la página, o el final
        let sig = d.nextElementSibling, before = 'end';
        while (sig) {
          const g = sig.classList.contains('grid') ? sig : sig.querySelector && sig.querySelector('.grid');
          if (g && g.dataset.gridId) { before = g.dataset.gridId; break; }
          sig = sig.nextElementSibling;
        }
        return { key: d.dataset.key, text: d.dataset.text, pageKey: p.dataset.pageKey, before };
      })),
    deletedDividers: [...deletedDivKeys],
  };
}

function saveLayout(silent) {
  localStorage.setItem(LS_KEY, JSON.stringify(layoutData()));
  clearTimeout(saveLayout._t);
  saveLayout._t = setTimeout(buildSidebar, 250);  // refrescar miniaturas
  if (!silent) setStatus('Disposición guardada en el navegador');
}

function applyLayout(data) {
  // compatibilidad: los layouts viejos eran solo el array de grids
  const grids = Array.isArray(data) ? data : (data.grids || []);
  const blockByKey = {}, gridById = {};
  $$('.block').forEach(b => blockByKey[b.dataset.key] = b);
  $$('.grid').forEach(g => gridById[g.dataset.gridId] = g);
  let moved = 0;
  grids.forEach(rec => {
    const g = gridById[rec.id];
    if (!g) return;
    if (rec.cols) {
      g.classList.remove('cols-1', 'cols-2', 'cols-3', 'cols-4');
      g.classList.add(rec.cols);
      const btn = g.parentNode.querySelector('.grid-cols-btn');
      if (btn) btn.textContent = '▤ ' + rec.cols.slice(5);
    }
    rec.blocks.forEach(k => { const b = blockByKey[k]; if (b) { g.appendChild(b); moved++; } });
  });
  if (!Array.isArray(data)) {
    (data.deleted || []).forEach(k => {
      const b = blockByKey[k];
      if (b) b.classList.add('deleted-block');
    });
    if (data.pageOrder && data.pageOrder.length) {
      const cont = $('#pages');
      const byKey = {};
      $$('.page').forEach(p => byKey[p.dataset.pageKey] = p);
      data.pageOrder.forEach(k => { if (byKey[k]) cont.appendChild(byKey[k]); });
    }
    if (data.dividers) {
      const existentes = {};
      $$('#pages .divider').forEach(d => existentes[d.dataset.key] = d);
      const usados = new Set();
      const pageByKey = {};
      $$('#pages > .page').forEach(p => pageByKey[p.dataset.pageKey] = p);
      data.dividers.forEach(rec => {
        let d = existentes[rec.key];
        if (!d) {
          // solo recrear marcadores personalizados; los generados que ya no
          // existen en el archivo son registros viejos -> ignorar
          if (!String(rec.key).startsWith('custom-')) return;
          d = makeDivider(rec.text, rec.key);
        }
        else if (d.dataset.text !== rec.text) { d.dataset.text = rec.text; prepDivider(d); }
        usados.add(rec.key);
        const page = pageByKey[rec.pageKey];
        if (!page) return;
        let ancla = null;
        if (rec.before !== 'end') {
          const g = page.querySelector('.grid[data-grid-id="' + rec.before + '"]');
          if (g) ancla = g.closest('.grid-wrap') || g;
        }
        if (ancla) page.insertBefore(d, ancla);
        else page.insertBefore(d, page.querySelector(':scope > .page-controls'));
      });
      (data.deletedDividers || []).forEach(k => {
        deletedDivKeys.add(k);
        if (existentes[k]) existentes[k].remove();
      });
    }
    updateTrash();
  }
  return moved;
}

function download(name, content, type) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([content], { type }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

function exportJSON() {
  download('tarifario_layout.json', JSON.stringify(layoutData(), null, 2), 'application/json');
  setStatus('Layout exportado (guárdalo para reaplicarlo tras regenerar)');
}

function importJSON(file) {
  const rd = new FileReader();
  rd.onload = () => {
    try {
      const n = applyLayout(JSON.parse(rd.result));
      saveLayout(true);
      setStatus('Layout aplicado (' + n + ' tablas reubicadas)');
    } catch (err) { setStatus('Error al leer el JSON: ' + err.message); }
  };
  rd.readAsText(file);
}

function exportHTML() {
  const clone = $('#pages').cloneNode(true);
  clone.querySelectorAll('.grid-cols-btn, .block-del, .page-controls, .block.deleted-block, .div-del')
    .forEach(e => e.remove());
  clone.querySelectorAll('.divider').forEach(d => {
    d.removeAttribute('draggable');
    d.removeAttribute('title');
    delete d.dataset.key;
  });
  clone.querySelectorAll('.grid-wrap').forEach(w => w.replaceWith(w.querySelector('.grid')));
  clone.querySelectorAll('.block').forEach(b => {
    b.removeAttribute('draggable');
    b.classList.remove('dragging');
    delete b.dataset.key;
  });
  clone.querySelectorAll('.grid').forEach(g => {
    g.classList.remove('dragover');
    delete g.dataset.gridId;
  });
  const css = $('#base-css').textContent;
  const html = '<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="UTF-8">\n' +
    '<title>Tarifario Rápido 2026</title>\n<style>' + css + '</style>\n</head>\n<body>\n' +
    clone.innerHTML + '\n</body>\n</html>';
  download('Tarifario_Personalizado_2026.html', html, 'text/html');
  setStatus('HTML exportado — ábrelo y usa Imprimir para el PDF');
}

function resetLayout() {
  if (!confirm('¿Restablecer la disposición original?')) return;
  localStorage.removeItem(LS_KEY);
  location.reload();
}

document.addEventListener('DOMContentLoaded', () => {
  assignKeys();
  addColsButtons();
  addDeleteButtons();
  addPageControls();
  $$('#pages .divider').forEach(prepDivider);
  $('#btn-marker').onclick = agregarMarcador;
  $('#btn-trash').onclick = restoreDeleted;
  $('#btn-pages').onclick = () => {
    const on = document.body.classList.toggle('with-sidebar');
    $('#sidebar').style.display = on ? '' : 'none';
  };
  document.body.classList.add('with-sidebar');
  const saved = localStorage.getItem(LS_KEY);
  if (saved) {
    try { applyLayout(JSON.parse(saved)); setStatus('Disposición previa restaurada'); }
    catch (e) { /* layout corrupto: ignorar */ }
  }
  buildSidebar();
  wireSidebar();
  $('#btn-save').onclick = () => saveLayout();
  $('#btn-export-json').onclick = exportJSON;
  $('#btn-export-html').onclick = exportHTML;
  $('#btn-print').onclick = () => window.print();
  $('#btn-reset').onclick = resetLayout;
  $('#file-import').onchange = e => { if (e.target.files[0]) importJSON(e.target.files[0]); e.target.value = ''; };
});
"""

EDITOR_WRAPPER = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Editor de Tarifarios 2026</title>
  <style id="base-css">{css}</style>
  <style>{editor_css}</style>
</head>
<body>
  <div class="toolbar">
    <b>Editor de Tarifarios</b>
    <button id="btn-save" type="button">💾 Guardar disposición</button>
    <button id="btn-export-json" type="button">⬇ Exportar layout (JSON)</button>
    <label><button type="button" onclick="document.getElementById('file-import').click()">⬆ Importar layout</button></label>
    <input type="file" id="file-import" accept="application/json" style="display:none">
    <button id="btn-export-html" type="button">📄 Exportar HTML final</button>
    <button id="btn-print" type="button">🖨 Imprimir / PDF</button>
    <button id="btn-trash" type="button" style="display:none">🗑 Restaurar tablas (0)</button>
    <button id="btn-marker" type="button">🏷 Marcador</button>
    <button id="btn-pages" type="button">📑 Hojas</button>
    <button id="btn-reset" type="button">↺ Restablecer</button>
    <span class="status" id="status"></span>
  </div>
  <div id="sidebar"></div>
  <div id="pages">
{body}
  </div>
  <script>{js}</script>
</body>
</html>"""


def generar_editor(P):
    OUT_HTML.mkdir(exist_ok=True)
    todas = "\n".join(html_page(cat, tit, items) for _, cat, tit, items in P)
    html = EDITOR_WRAPPER.format(css=base.CSS + CSS_EXTRA, editor_css=EDITOR_CSS, body=todas, js=EDITOR_JS)
    out = OUT_HTML / "Tarifario_Editor_2026.html"
    out.write_text(html, encoding="utf-8")
    print(f"Generado: {out}")


# ── Render Word ──────────────────────────────────────────────────────────────
def docx_page(doc, category, title, items):
    import generar_tarifarios as gt

    gt.page_banner(doc, title, updated=FECHA)
    for item in items:
        if item[0] == "divider":
            cls = DIV_CLASS.get(nrm(item[1]), "")
            color = {"d-exc": gt.RED, "d-nivel": gt.ORANGE}.get(cls, gt.BLUE)
            gt.section_header(doc, item[1], bg=color)
        else:
            kind, cols, blocks = item
            slots = [(b[0], b[1], b[2]) for b in blocks]
            gt.columns_layout(doc, slots, n_cols=cols, exception=(kind == "grid_exc"))


def _doc_base():
    import generar_tarifarios as gt
    from docx import Document
    from docx.shared import Pt

    d = Document()
    gt.set_landscape(d)
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10)
    st.paragraph_format.space_before = Pt(0)
    st.paragraph_format.space_after = Pt(4)
    return d


def generar_docx(P):
    OUT_DOCX.mkdir(exist_ok=True)
    doc = _doc_base()
    for i, (name, cat, tit, items) in enumerate(P):
        if i > 0:
            doc.add_page_break()
        docx_page(doc, cat, tit, items)
    out = OUT_DOCX / "Tarifario_Completo_2026.docx"
    doc.save(str(out))
    print(f"Generado: {out}")

    for name, cat, tit, items in P:
        d = _doc_base()
        docx_page(d, cat, tit, items)
        p = OUT_DOCX / f"Tarifario_{name}_2026.docx"
        d.save(str(p))
        print(f"  + {p.name}")


if __name__ == "__main__":
    P = paginas(Filas(cargar_filas()))
    if "--docx" not in sys.argv:
        generar_html(P)
        generar_editor(P)
    if "--html" not in sys.argv:
        generar_docx(P)
