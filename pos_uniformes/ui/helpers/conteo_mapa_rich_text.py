"""El mapa de conteos como texto enriquecido de Qt (sin WebEngine).

QLabel entiende un subconjunto de HTML: tablas con `bgcolor` y `width`,
colores y enlaces. Con eso se pintan los mosaicos (una celda por escuela),
las barras (una tabla de tres celdas con anchos proporcionales) y las fichas
de talla. Los enlaces `href="e19"` / `href="bPantalón"` / `href="mapa"` los
atiende el widget para cambiar de capa. Puro: recibe el dict de
`conteo_mapa_service.todo()` y devuelve HTML.
"""

from __future__ import annotations

from html import escape

VERDE, AMBAR, GRIS, FONDO = "#3d6b2f", "#c98a2b", "#b9b0a4", "#e6ddd0"
COLOR_ESTADO = {"al_dia": VERDE, "vieja": AMBAR, "nunca": GRIS}
FONDO_TALLA = {"al_dia": "#d9ecd0", "vieja": "#f6e3c6", "nunca": "#eee9e1"}
TEXTO_TALLA = {"al_dia": VERDE, "vieja": "#8a5a12", "nunca": "#6f675c"}
ORDEN_NIVELES = ["Preescolar", "Primaria", "Secundaria", "Preparatoria", "Varios niveles", "Sin nivel"]


def barra(c: dict, ancho: int = 100) -> str:
    """Tres celdas de color con ancho proporcional; la de fondo rellena lo que falte."""
    total = c.get("tallas") or 1
    partes = []
    for clave, color in (("al_dia", VERDE), ("viejas", AMBAR), ("nunca", GRIS)):
        w = round(ancho * c.get(clave, 0) / total)
        if w > 0:
            partes.append(f'<td width="{w}" bgcolor="{color}"></td>')
    if not partes:
        partes.append(f'<td width="{ancho}" bgcolor="{FONDO}"></td>')
    return f'<table cellspacing="0" cellpadding="0" width="{ancho}"><tr>{"".join(partes)}</tr></table>'


def texto(c: dict) -> str:
    u = c.get("ultimo_dias")
    cuando = "nunca" if u is None else ("hoy" if u == 0 else f"hace {u} d")
    return f"{c.get('pct_al_dia', 0)}% al día · {cuando}"


def _mosaico(e: dict, href: str, ancho_barra: int) -> str:
    color = COLOR_ESTADO.get(e.get("estado", "nunca"), GRIS)
    fondo = "#fff4e5" if e.get("en_proceso") else "#fffdf8"
    linea = escape(texto(e)) + (f" · {escape(e['quien'])}" if e.get("quien") and not e.get("en_proceso") else "")
    proceso = (f'<br><span style="color:#b45309;font-weight:700;font-size:11px">En proceso · {escape(e["en_proceso"])}</span>'
               if e.get("en_proceso") else "")
    return (
        f'<table cellspacing="0" cellpadding="6" width="100%" bgcolor="{fondo}"><tr>'
        f'<td width="5" bgcolor="{color}"></td>'
        f'<td><a href="{escape(href)}" style="text-decoration:none;color:#2c2a27"><b>{escape(e["nombre"])}</b></a><br>'
        f'{barra(e, ancho_barra)}<span style="color:#5f594f;font-size:11px">{linea}</span>{proceso}</td>'
        f"</tr></table>"
    )


def _rejilla(items: list[str], columnas: int) -> str:
    filas = []
    for i in range(0, len(items), columnas):
        celdas = items[i:i + columnas] + [""] * (columnas - len(items[i:i + columnas]))
        filas.append("<tr>" + "".join(f'<td width="{100 // columnas}%" valign="top">{c}</td>' for c in celdas) + "</tr>")
    return f'<table cellspacing="6" cellpadding="0" width="100%">{"".join(filas)}</table>'


LEYENDA = (
    f'<span style="font-size:11px;color:#5f594f">'
    f'<span style="background-color:{VERDE};color:{VERDE}">&nbsp;&nbsp;</span> al día &nbsp; '
    f'<span style="background-color:{AMBAR};color:{AMBAR}">&nbsp;&nbsp;</span> viejo &nbsp; '
    f'<span style="background-color:{GRIS};color:{GRIS}">&nbsp;&nbsp;</span> nunca &nbsp; '
    f'<span style="background-color:#fff4e5;color:#fff4e5">&nbsp;&nbsp;</span> en proceso</span>'
)


def mapa(datos: dict, *, columnas: int = 4, filtro: str = "") -> str:
    """Capa 1: total + mosaicos por nivel + básicos por tipo."""
    t = datos["total"]
    q = filtro.strip().lower()
    partes = [
        f'<p style="margin:0"><b>Toda la tienda · {t["tallas"]:,} tallas</b> &nbsp; '
        f'<span style="color:#5f594f;font-size:12px">{t["al_dia"]:,} al día · {t["viejas"]:,} viejas · {t["nunca"]:,} nunca</span></p>',
        barra(t, 600), LEYENDA,
    ]
    escuelas = [e for e in datos["escuelas"] if not q or q in e["nombre"].lower()]
    niveles = sorted({e["nivel"] for e in escuelas}, key=lambda n: (ORDEN_NIVELES.index(n) if n in ORDEN_NIVELES else 99, n))
    for n in niveles:
        lista = [e for e in escuelas if e["nivel"] == n]
        partes.append(f'<p style="margin:14px 0 2px;font-size:11px;font-weight:700;color:#5f594f">{escape(n.upper())} · {len(lista)}</p>')
        partes.append(_rejilla([_mosaico(e, f"e{e['escuela_id']}", 160) for e in lista], columnas))
    if not q and datos.get("basicos"):
        partes.append(f'<p style="margin:14px 0 2px;font-size:11px;font-weight:700;color:#5f594f">BÁSICOS · {len(datos["basicos"])} TIPOS</p>')
        partes.append(_rejilla([_mosaico({**b, "nombre": b["tipo_pieza"]}, f"b{b['tipo_pieza']}", 160) for b in datos["basicos"]], columnas))
    if q and not escuelas:
        partes.append('<p style="color:#5f594f">Ninguna escuela con ese nombre.</p>')
    return "".join(partes)


def detalle(d: dict, *, abiertas: set[int] | None = None) -> str:
    """Capa 2 + 3: las prendas con su barra; las de `abiertas` muestran sus tallas."""
    abiertas = abiertas or set()
    partes = [
        f'<p style="margin:0"><a href="mapa" style="color:#8a4326;font-weight:700;text-decoration:none">‹ Mapa</a> &nbsp; '
        f'<b style="font-size:16px">{escape(d["titulo"])}</b> &nbsp; <span style="color:#5f594f;font-size:12px">{d["tallas"]} tallas · {escape(texto(d))}</span></p>',
        barra(d, 600), LEYENDA,
    ]
    for i, p in enumerate(d["prendas"]):
        flecha = "▾" if i in abiertas else "▸"
        tipo = f'{escape(p["tipo_pieza"])} · ' if p.get("tipo_pieza") else ""
        partes.append(
            f'<table cellspacing="0" cellpadding="6" width="100%" bgcolor="#fffdf8" style="margin-top:6px"><tr><td>'
            f'<a href="p{i}" style="text-decoration:none;color:#2c2a27"><b>{flecha} {escape(p["nombre"])}</b></a> &nbsp; '
            f'<span style="color:#5f594f;font-size:11px">{tipo}{p["tallas"]} tallas · {escape(texto(p))}</span><br>{barra(p, 600)}'
        )
        if i in abiertas:
            fichas = []
            for tl in p["tallas_detalle"]:
                est = tl["estado"]
                dias = "nunca" if tl["dias"] is None else ("hoy" if tl["dias"] == 0 else f"hace {tl['dias']} d")
                color = tl.get("color") or ""
                if color.strip().lower() in ("sin color", "unico", "único"):
                    color = ""
                fichas.append(
                    f'<td bgcolor="{FONDO_TALLA[est]}" style="color:{TEXTO_TALLA[est]}"><b>{escape(tl["talla"])}{(" " + escape(color)) if color else ""}</b>'
                    f'<br><span style="font-size:10px">{dias} · {tl["stock"]} pz</span></td>'
                )
            filas = ["<tr>" + "".join(fichas[j:j + 8]) + "</tr>" for j in range(0, len(fichas), 8)]
            partes.append(f'<br><table cellspacing="4" cellpadding="5">{"".join(filas)}</table>')
        partes.append("</td></tr></table>")
    if not d["prendas"]:
        partes.append('<p style="color:#5f594f">Sin prendas para contar.</p>')
    return "".join(partes)
