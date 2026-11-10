#!/usr/bin/env python3
"""Busca productos "hermanos" para dar de alta uno nuevo coherente con el catálogo.

SOLO LECTURA: la conexión se abre con default_transaction_read_only=on.

Uso (desde la raíz del repo, con el Python del proyecto):
    python .claude/skills/alta-productos/scripts/buscar_hermanos.py \
        --pieza "Playera" --prenda Deportivo --nivel Secundaria --escuela "Técnica 18"

Todos los filtros son opcionales y no distinguen mayúsculas ni acentos.
Conexión: --db-url, o la configuración del proyecto (pos_uniformes.env / variables
POS_UNIFORMES_DB_*). Para la caja: --db-url postgresql+psycopg://usuario:clave@host:5432/pos_uniformes

Imprime:
  1. Valores de catálogo que coinciden con lo pedido y CASI-DUPLICADOS
     (p. ej. "Básico" vs "Basico") para no crear otro.
  2. Hermanos: productos con la misma pieza/prenda/nivel en otras escuelas,
     con su patrón (nombre sin escuela, marca, categoría, género, escudo,
     atributo, tallas, colores, precio por talla).
  3. Lo que ya existe para esa escuela (para no duplicar) y su uniforme.
"""
from __future__ import annotations

import argparse
import difflib
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import create_engine, text

TALLA_ORDEN = ["2", "4", "6", "8", "10", "12", "14", "16", "18", "28", "30", "32", "34", "36",
               "38", "40", "42", "44", "46", "CH", "MD", "GD", "EXG", "UNI"]
CATALOGOS = {
    "escuela": "escuela",
    "prenda": "tipo_prenda",
    "pieza": "tipo_pieza",
    "nivel": "nivel_educativo",
    "marca": "marca",
    "categoria": "categoria",
    "atributo": "atributo_producto",
}


def norm(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", (value or "").strip().lower())
    return " ".join("".join(c for c in value if not unicodedata.combining(c)).split())


def parecido(a: str, b: str) -> bool:
    """Contención, palabras en común (sin las vacías) o nombres casi iguales."""
    na, nb = norm(a), norm(b)
    if na in nb or nb in na:
        return True
    vacias = {"de", "del", "la", "el", "los", "las", "y"}
    ta, tb = set(na.split()) - vacias, set(nb.split()) - vacias
    if ta & tb:
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.75


def orden_talla(talla: str) -> tuple[int, str]:
    t = talla.strip().upper()
    return (TALLA_ORDEN.index(t), t) if t in TALLA_ORDEN else (len(TALLA_ORDEN), t)


def resolver_db_url(cli_url: str | None) -> str:
    if cli_url:
        return cli_url
    raiz = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(raiz))
    from pos_uniformes.utils.config import settings  # noqa: E402

    return settings.database_url


def cargar_catalogo(conn, tabla: str) -> list[str]:
    return [r[0] for r in conn.execute(text(f"SELECT nombre FROM {tabla} ORDER BY nombre"))]


def seccion_catalogos(conn, pedidos: dict[str, str | None]) -> None:
    print("## 1. Catálogos")
    for clave, tabla in CATALOGOS.items():
        valores = cargar_catalogo(conn, tabla)
        grupos: dict[str, list[str]] = defaultdict(list)
        for v in valores:
            grupos[norm(v)].append(v)
        casi = [g for g in grupos.values() if len(g) > 1]
        pedido = pedidos.get(clave)
        linea = f"- {clave} ({tabla}, {len(valores)} valores)"
        if pedido:
            exactos = grupos.get(norm(pedido), [])
            parecidos = [v for v in valores if v not in exactos and parecido(pedido, v)][:8]
            if exactos:
                linea += f": «{pedido}» EXISTE como {exactos}"
            else:
                linea += f": «{pedido}» NO EXISTE"
            if parecidos:
                linea += f" · parecidos: {parecidos}"
        print(linea)
        if casi:
            print(f"    ⚠ casi-duplicados ya en la DB: {casi}")
        if clave in {"prenda", "nivel", "categoria"} or (clave == "pieza" and not pedido):
            print(f"    valores: {', '.join(valores)}")


FILAS_SQL = """
SELECT p.id, p.nombre, p.nombre_base, p.genero, p.escudo, p.activo,
       e.nombre AS escuela, tpr.nombre AS prenda, tpi.nombre AS pieza,
       ne.nombre AS nivel, m.nombre AS marca, c.nombre AS categoria, a.nombre AS atributo,
       v.sku, v.talla, v.color, v.precio_venta, v.activo AS v_activo
FROM producto p
JOIN marca m ON m.id = p.marca_id
JOIN categoria c ON c.id = p.categoria_id
LEFT JOIN escuela e ON e.id = p.escuela_id
LEFT JOIN tipo_prenda tpr ON tpr.id = p.tipo_prenda_id
LEFT JOIN tipo_pieza tpi ON tpi.id = p.tipo_pieza_id
LEFT JOIN nivel_educativo ne ON ne.id = p.nivel_educativo_id
LEFT JOIN atributo_producto a ON a.id = p.atributo_id
LEFT JOIN variante v ON v.producto_id = p.id
WHERE p.activo
"""


def agrupar(filas) -> dict[int, dict]:
    productos: dict[int, dict] = {}
    for f in filas:
        p = productos.setdefault(f.id, {
            "nombre": f.nombre, "nombre_base": f.nombre_base, "escuela": f.escuela,
            "prenda": f.prenda, "pieza": f.pieza, "nivel": f.nivel, "marca": f.marca,
            "categoria": f.categoria, "atributo": f.atributo, "genero": f.genero,
            "escudo": f.escudo, "variantes": [],
        })
        if f.sku and f.v_activo:
            p["variantes"].append((f.talla, f.color, f.precio_venta, f.sku))
    return productos


def nombre_sin_escuela(p: dict) -> str:
    nombre = p["nombre_base"] or p["nombre"]
    if p["escuela"] and nombre.endswith(p["escuela"]):
        nombre = nombre[: -len(p["escuela"])].strip()
    return nombre


def coincide(p: dict, clave: str, pedido: str | None) -> bool:
    return not pedido or norm(p[clave]) == norm(pedido)


def describir(p: dict, indent: str = "  ") -> str:
    tallas = sorted({t for t, *_ in p["variantes"]}, key=orden_talla)
    colores = Counter(c for _, c, *_ in p["variantes"])
    precios: dict[str, set] = defaultdict(set)
    for t, _, precio, _ in p["variantes"]:
        precios[t].add(f"{precio:.0f}")
    escalera = " ".join(f"{t}:{'/'.join(sorted(precios[t]))}" for t in tallas)
    skus = sorted(s for *_, s in p["variantes"])
    return (
        f"{indent}«{p['nombre']}» | base «{nombre_sin_escuela(p)}» | {p['prenda']} · {p['pieza']} · "
        f"{p['nivel']} | marca {p['marca']} · cat {p['categoria']} · atrib {p['atributo']} · "
        f"género {p['genero']} · escudo {p['escudo']}\n"
        f"{indent}  tallas {len(tallas)}: {escalera or '(sin variantes)'}\n"
        f"{indent}  colores: {dict(colores) or '-'} · SKUs {skus[0] if skus else '-'}…{skus[-1] if skus else ''}"
    )


def seccion_hermanos(productos: dict[int, dict], args, limite: int) -> None:
    print("\n## 2. Hermanos (misma pieza/prenda/nivel, otras escuelas)")
    hermanos = [
        p for p in productos.values()
        if coincide(p, "pieza", args.pieza) and coincide(p, "prenda", args.prenda)
        and coincide(p, "nivel", args.nivel)
        and not (args.escuela and norm(p["escuela"]) == norm(args.escuela))
    ]
    if not hermanos and args.nivel:
        print(f"  (ninguno con nivel {args.nivel}; se relaja el nivel)")
        hermanos = [
            p for p in productos.values()
            if coincide(p, "pieza", args.pieza) and coincide(p, "prenda", args.prenda)
        ]
    if not hermanos:
        print("  (ninguno: producto sin precedente, revisar con Daniel)")
        return

    def resumen(campo: str) -> str:
        cuenta = Counter(p[campo] for p in hermanos)
        return ", ".join(f"{k} ×{n}" for k, n in cuenta.most_common(5))

    print(f"  {len(hermanos)} hermanos. Patrón dominante:")
    for campo in ("marca", "categoria", "atributo", "genero", "escudo", "prenda", "nivel"):
        print(f"    {campo}: {resumen(campo)}")
    bases = Counter(nombre_sin_escuela(p) for p in hermanos)
    print(f"    nombre (sin escuela): {', '.join(f'«{k}» ×{n}' for k, n in bases.most_common(6))}")
    juegos = Counter(
        " ".join(sorted({t for t, *_ in p["variantes"]}, key=orden_talla)) for p in hermanos
    )
    print("    juegos de tallas: " + " | ".join(f"[{k}] ×{n}" for k, n in juegos.most_common(4)))
    precio_talla: dict[str, Counter] = defaultdict(Counter)
    for p in hermanos:
        for t, _, precio, _ in p["variantes"]:
            precio_talla[t][f"{precio:.0f}"] += 1
    modal = " ".join(
        f"{t}:{c.most_common(1)[0][0]}" for t, c in sorted(precio_talla.items(), key=lambda x: orden_talla(x[0]))
    )
    print(f"    precio más común por talla: {modal}")
    print(f"  Ejemplos (hasta {limite}):")
    for p in sorted(hermanos, key=lambda p: -len(p["variantes"]))[:limite]:
        print(describir(p, "    "))


def seccion_escuela(conn, productos: dict[int, dict], escuela: str) -> None:
    print(f"\n## 3. Lo que ya existe para «{escuela}»")
    propios = [p for p in productos.values() if norm(p["escuela"]) == norm(escuela)]
    if not propios:
        print("  (la escuela no tiene productos activos o no existe con ese nombre exacto)")
    for p in sorted(propios, key=lambda p: (p["prenda"] or "", p["pieza"] or "")):
        tallas = sorted({t for t, *_ in p["variantes"]}, key=orden_talla)
        print(f"  - «{p['nombre']}» {p['prenda']} · {p['pieza']} · {p['nivel']} · {len(tallas)} tallas")
    try:
        piezas = conn.execute(text("""
            SELECT up.grupo, pr.nombre FROM uniforme u
            JOIN escuela e ON e.id = u.escuela_id
            JOIN uniforme_pieza up ON up.uniforme_id = u.id AND up.activo
            JOIN producto pr ON pr.id = up.producto_id
            WHERE e.nombre = :e ORDER BY up.grupo, up.orden
        """), {"e": propios[0]["escuela"] if propios else escuela}).all()
        if piezas:
            print("  Uniforme armado: " + "; ".join(f"{g}: {n}" for g, n in piezas))
        else:
            print("  Uniforme: no armado (o la escuela no tiene uniforme)")
    except Exception as exc:  # tablas de uniforme ausentes en DBs viejas
        conn.rollback()
        print(f"  Uniforme: no disponible en esta DB ({type(exc).__name__})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pieza")
    ap.add_argument("--prenda")
    ap.add_argument("--nivel")
    ap.add_argument("--escuela")
    ap.add_argument("--marca")
    ap.add_argument("--categoria")
    ap.add_argument("--atributo")
    ap.add_argument("--limite", type=int, default=4, help="ejemplos de hermanos a mostrar")
    ap.add_argument("--db-url")
    args = ap.parse_args()

    engine = create_engine(
        resolver_db_url(args.db_url),
        connect_args={"options": "-c default_transaction_read_only=on", "connect_timeout": 5},
    )
    with engine.connect() as conn:
        host = engine.url.host or "local"
        print(f"DB: {host}/{engine.url.database} (solo lectura)\n")
        seccion_catalogos(conn, vars(args))
        productos = agrupar(conn.execute(text(FILAS_SQL)).all())
        seccion_hermanos(productos, args, args.limite)
        if args.escuela:
            seccion_escuela(conn, productos, args.escuela)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
