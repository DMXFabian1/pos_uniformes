#!/usr/bin/env python3
"""Genera mapa_escuelas_san_felipe.html con todas las escuelas del mercado.

Fuente: directorio SEP publicado en escuelasmex.com (fichas por CCT, con
coordenadas). Descarga listados por categoría del municipio San Felipe, Gto.,
filtra a cabecera + comunidades cliente (+ SABES/telebach de todo el
municipio), cruza contra el catálogo del POS para marcar clientes e inyecta
los datos en plantilla_mapa.html.

Uso:
    python3 mapas_escuelas/generar_datos_escuelas.py

Las fichas HTML se cachean en mapas_escuelas/cache_fichas/ — la primera
corrida tarda ~2 min; después es instantáneo salvo escuelas nuevas.
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import urllib.request
from html import unescape
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache_fichas"
PLANTILLA = BASE_DIR / "plantilla_mapa.html"
SALIDA = BASE_DIR / "mapa_escuelas_san_felipe.html"
CATALOG_CACHE = BASE_DIR.parent / "pos_uniformes" / "data" / "catalog_cache.json"

SITIO = "https://escuelasmex.com"
PAUSA_S = 0.4
UA = {"User-Agent": "Mozilla/5.0 (mapa-escuelas-pos-uniformes)"}

# Listados por categoría. Se prueban ambas estructuras de URL del sitio.
CATEGORIAS = [
    ("educacion-basica/preescolar-general", "general"),
    ("educacion-basica/preescolar-comunitario", "conafe"),
    ("preescolar-conafe", "conafe"),
    ("educacion-basica/primaria-general", "general"),
    ("educacion-basica/primaria-comunitaria", "conafe"),
    ("primaria-conafe", "conafe"),
    ("educacion-basica/secundaria-general", "general"),
    ("educacion-basica/secundaria-tecnica", "tecnica"),
    ("educacion-basica/telesecundaria", "telesec"),
    ("educacion-media-superior/bachillerato-general", "general"),
    ("educacion-media-superior/bachillerato-tecnologico", "tecnologico"),
    ("educacion-media-superior/bachillerato-profesional-tecnico-bachiller", "conalep"),
]

# Nivel según las letras del CCT (posiciones 2:5, ej. 11DJN... -> DJN).
NIVEL_POR_CCT = {
    "DJN": "Pre", "EJN": "Pre", "PJN": "Pre", "KJN": "Pre",
    "DPR": "Pri", "EPR": "Pri", "PPR": "Pri", "KPR": "Pri", "DBA": "Pri",
    "DES": "Sec", "EES": "Sec", "PES": "Sec", "DST": "Sec", "ETV": "Sec", "KTV": "Sec",
    "DCT": "Bach", "ETC": "Bach", "ETH": "Bach", "ETK": "Bach", "DPT": "Bach",
    "PBH": "Bach", "PCB": "Bach",
    "DER": "Otro",
}
TIPO_POR_CCT = {"ETH": "sabes", "ETK": "telebach", "ETV": "telesec", "KJN": "conafe",
                "KPR": "conafe", "KTV": "conafe", "DST": "tecnica", "DPT": "conalep",
                "DER": "capacitacion"}

CABECERA = "san felipe"
# Comunidades donde ya hay escuelas cliente.
COMUNIDADES_CLIENTE = [
    "jaral de berrio", "estacion jaral", "san bartolo de berrio",
    "sauceda de la luz", "santa rosa", "san pedro de almoloya", "huizache",
    "mastranto del refugio", "aranjuez", "miguel hidalgo", "cueritos",
    "la huerta", "san juan de llanos", "salto del ahogado", "el carreton",
]

# Escuelas del POS -> CCT del directorio SEP (investigado ago-2026).
# probable=True cuando el nombre se repite en varias comunidades y se eligió
# la del cluster donde ya hay clientes.
CLIENTES_CCT: dict[str, dict] = {
    "11DJN0152R": {"pos": "Margarita Paz Paredes"},
    "11DJN2847M": {"pos": "Frida Kahlo"},
    "11EJN0336X": {"pos": "Sor Juana Inés de la Cruz"},
    "11EJN0093R": {"pos": "Blanca Verónica Soto Martínez Príncipes"},
    "11DJN0004I": {"pos": "Jorge Cantor"},
    "11DJN0503E": {"pos": "Patria"},
    "11EJN0269P": {"pos": "Vidal Alcocer"},
    "11DJN2388R": {"pos": "Álvaro Obregón", "probable": True},
    "11DPR0013G": {"pos": "Ignacio Allende"},
    "11DPR3467A": {"pos": "Albino García Ramos"},
    "11DPR0110I": {"pos": "Miguel Hidalgo"},
    "11DPR0587T": {"pos": "Justo Sierra"},
    "11DPR1915C": {"pos": "Ignacio Zaragoza"},
    "11DPR2812N": {"pos": "Francisco Villa"},
    "11DPR3415V": {"pos": "Himno Nacional"},
    "11DPR3397W": {"pos": "Benito Juárez"},
    "11DPR3992V": {"pos": "Ignacio Ramirez Lopez"},
    "11EPR0435N": {"pos": "Miguel Campuzano"},
    "11EPR0530R": {"pos": "Club Rotario"},
    "11PPR0445Z": {"pos": "Colegio Motolinea"},
    "11PJN0546H": {"pos": "Colegio Motolinea"},
    "11PES0197B": {"pos": "Colegio Motolinea"},
    "11DES0014Z": {"pos": "Práxedis Guerrero"},
    "11DPR0217A": {"pos": "Práxedis Guerrero"},
    "11DES0110B": {"pos": "Bicentenario"},
    "11ETV0522H": {"pos": "Telesecundaria 512"},
    "11ETV0459W": {"pos": "Telesecundaria 454"},
    "11ETV0601U": {"pos": "Telesecundaria 600"},
    "11ETV0642U": {"pos": "ESTV 663"},
    "11ETV0155C": {"pos": "ESTV 154"},
    "11ETV0230T": {"pos": "Santa Rosa 238"},
    "11DST0018N": {"pos": "Técnica de San Bartolo", "probable": True},
    "11DCT0003K": {"pos": "CBTIS 148"},
    "11ETC0041M": {"pos": "CECYTE"},
    "11ETH0202D": {"pos": "SABES"},
    "11DPT0014U": {"pos": "Conalep"},
    "11EPR0717V": {"pos": "Narciso Mendoza"},
    "11DPR2071K": {"pos": "Emiliano Zapata", "probable": True},
    "11DPR0218Z": {"pos": "José María Morelos y Pavón"},
    "11DPR3095A": {"pos": "Adolfo Lopez Mateo", "probable": True},
    "11DPR1129N": {"pos": "José María Morelos", "probable": True},
    "11DPR0891C": {"pos": "Huizache", "probable": True},
    "11DPR0892B": {"pos": "J. Guadalupe Victoria", "probable": True},
    "11DPR1288B": {"pos": "Niños Héroes", "probable": True},
    "11DPR2574C": {"pos": "Niños Héroes de Miguel Hidalgo"},
}

# Sin ficha en el directorio SEP: se agregan a mano.
EXTRAS = [
    {"cct": "UVEG", "nombre": "UVEG", "nivel": "Bach", "tipo": "general",
     "turno": "", "domicilio": "Prol. Aldama 925, Centro Impulso Social",
     "localidad": "San Felipe", "lat": 21.4750453, "lon": -101.2244897,
     "cliente": True, "pos": "UVEG", "probable": True},
]

PENDIENTES = [
    "Jean Piaget (Pre) — no aparece en el directorio SEP de San Felipe",
    "Vicente Guerrero (Pre+Pri) — 3 candidatas: San Isidro y Capellanía, La Estanzuela, La Quemada",
    "Palacio (Pri) — sin escuela ni localidad con ese nombre en el directorio",
]


def normaliza(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.lower().strip()


def descarga(url: str, destino: Path | None = None) -> str | None:
    if destino is not None and destino.exists() and destino.stat().st_size > 0:
        return destino.read_text(encoding="utf-8", errors="ignore")
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None
    time.sleep(PAUSA_S)
    if destino is not None:
        destino.write_text(html, encoding="utf-8")
    return html


def links_directorio(html: str) -> set[str]:
    return set(re.findall(r'href="(/directorio/[^"]+)"', html or ""))


def junta_listados() -> dict[str, str]:
    """Devuelve {slug_directorio: tipo_categoria} de todas las categorías."""
    encontrados: dict[str, str] = {}
    for categoria, tipo in CATEGORIAS:
        urls_base = [
            f"{SITIO}/{categoria}/guanajuato/san-felipe",
            f"{SITIO}/{categoria}/municipio/san-felipe-guanajuato",
        ]
        slug_cat = categoria.replace("/", "_")
        base_ok = None
        for j, u in enumerate(urls_base):
            html = descarga(u, CACHE_DIR / f"listado_{slug_cat}_v{j}_p1.html")
            if html and links_directorio(html):
                base_ok, base_j = u, j
                break
        if base_ok is None:
            print(f"  [aviso] sin resultados: {categoria}")
            continue
        vistos: set[str] = set()
        pagina = 1
        while pagina <= 10:
            url = base_ok if pagina == 1 else f"{base_ok}/page/{pagina}"
            html = descarga(url, CACHE_DIR / f"listado_{slug_cat}_v{base_j}_p{pagina}.html")
            nuevos = links_directorio(html) - vistos
            if not nuevos:
                break
            vistos |= nuevos
            pagina += 1
        for slug in vistos:
            encontrados.setdefault(slug, tipo)
        print(f"  {categoria}: {len(vistos)} escuelas")
    return encontrados


def parsea_ficha(html: str, cct: str) -> dict | None:
    texto = unescape(re.sub(r"<script.*?</script>", " ", html, flags=re.S))
    lineas = [l.strip() for l in re.sub(r"<[^>]+>", "\n", texto).split("\n") if l.strip()]

    nombre = ""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if m:
        nombre = unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        nombre = re.sub(r"\s*CCT.*$", "", nombre).strip()
        nombre = re.sub(r"^(Preescolar|Primaria|Secundaria|Bachillerato)\s+", "", nombre)

    # Localidad: del párrafo descriptivo "a la comunidad de X, San Felipe (Guanajuato)"
    loc = ""
    m = re.search(r"comunidad de (.+?), San Felipe \(Guanajuato\)", texto)
    if m:
        loc = m.group(1).strip()
    if not loc:
        # fallback: línea estructurada "calle, colonia, localidad"
        for i, l in enumerate(lineas):
            if l.startswith("Domicilio") and i + 1 < len(lineas):
                partes = [p.strip() for p in lineas[i + 1].split(",")]
                if len(partes) >= 3 and "CP." not in lineas[i + 1]:
                    loc = partes[-1]
                    break

    domicilio = next(
        (lineas[i + 1] for i, l in enumerate(lineas)
         if l.startswith("Domicilio") and i + 1 < len(lineas)), "")
    domicilio = re.sub(r",?\s*San Felipe, Guanajuato.*$", "", domicilio).strip()

    turno = next((l for l in lineas if l in ("Matutino", "Vespertino", "Continuo",
                                             "Discontinuo", "Nocturno")), "")

    lat = re.search(r"(21\.\d{2,8})", html)
    lon = re.search(r"(-10[01]\.\d{1,8})", html)
    if not (lat and lon):
        return None
    return {
        "cct": cct, "nombre": nombre, "turno": turno, "domicilio": domicilio,
        "localidad": loc, "lat": float(lat.group(1)), "lon": float(lon.group(1)),
    }


def en_mercado(escuela: dict) -> bool:
    tipo = escuela.get("tipo", "")
    if tipo in ("sabes", "telebach"):
        return True  # cobertura de media superior de todo el municipio
    loc = normaliza(escuela.get("localidad", ""))
    if not loc:
        return False
    if loc == CABECERA or loc.startswith("san felipe"):
        return True
    return any(c in loc for c in COMUNIDADES_CLIENTE)


def carga_clientes_pos() -> set[str]:
    try:
        data = json.loads(CATALOG_CACHE.read_text(encoding="utf-8"))
        return {r["escuela_nombre"] for r in data["rows"] if r.get("escuela_nombre")}
    except Exception:
        return set()


def main() -> int:
    CACHE_DIR.mkdir(exist_ok=True)
    print("Descargando listados por categoría…")
    slugs = junta_listados()
    print(f"Total fichas en listados: {len(slugs)}")

    escuelas: list[dict] = []
    sin_datos: list[str] = []
    for slug, tipo_cat in sorted(slugs.items()):
        cct = slug.strip("/").split("/")[1]  # /directorio/<CCT>/<nombre>-slug
        html = descarga(f"{SITIO}{slug}", CACHE_DIR / f"{cct}.html")
        if not html:
            sin_datos.append(cct)
            continue
        ficha = parsea_ficha(html, cct)
        if ficha is None:
            sin_datos.append(cct)
            continue
        letras = cct[2:5]
        ficha["nivel"] = NIVEL_POR_CCT.get(letras, "Otro")
        ficha["tipo"] = TIPO_POR_CCT.get(letras, tipo_cat)
        if cct[2] == "P":
            ficha["tipo"] = "particular"
        escuelas.append(ficha)

    mercado = [e for e in escuelas if en_mercado(e)]

    nombres_pos = carga_clientes_pos()
    clientes = 0
    for e in mercado:
        info = CLIENTES_CCT.get(e["cct"])
        e["cliente"] = bool(info)
        e["pos"] = info["pos"] if info else ""
        e["probable"] = bool(info and info.get("probable"))
        if info:
            clientes += 1
            if info["pos"] not in nombres_pos:
                print(f"  [aviso] '{info['pos']}' no está en catalog_cache")
    mercado.extend(EXTRAS)
    clientes += sum(1 for e in EXTRAS if e["cliente"])

    faltantes = [i["pos"] for c, i in CLIENTES_CCT.items()
                 if c not in {e['cct'] for e in mercado}]
    if faltantes:
        print(f"  [aviso] clientes con CCT fuera del resultado: {faltantes}")

    mercado.sort(key=lambda e: (normaliza(e["localidad"]) != CABECERA,
                                normaliza(e["localidad"]), e["nivel"], normaliza(e["nombre"])))

    print(f"Escuelas en el mercado: {len(mercado)} ({clientes} clientes)")
    if sin_datos:
        print(f"Fichas sin coordenadas/datos (omitidas): {len(sin_datos)}: {sin_datos}")

    plantilla = PLANTILLA.read_text(encoding="utf-8")
    datos_js = ("const ESCUELAS = " + json.dumps(mercado, ensure_ascii=False)
                + ";\nconst PENDIENTES = " + json.dumps(PENDIENTES, ensure_ascii=False) + ";")
    if "/*__DATOS__*/" not in plantilla:
        print("ERROR: plantilla sin marcador /*__DATOS__*/", file=sys.stderr)
        return 1
    SALIDA.write_text(plantilla.replace("/*__DATOS__*/", datos_js), encoding="utf-8")
    print(f"Generado: {SALIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
