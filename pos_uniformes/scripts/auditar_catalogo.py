"""Auditor de inconsistencias en el catálogo de productos.

Detecta:
  1. Color en nombre_base pero todas las variantes son "Sin color"
  2. Color en nombre_base Y en variante (redundancia — nombre debería ser neutro)
  3. Mezcla en mismo producto: algunas variantes "Sin color", otras con color explícito
  4. Productos activos sin variantes activas

Uso:
    python3 pos_uniformes/scripts/auditar_catalogo.py
    python3 pos_uniformes/scripts/auditar_catalogo.py --json   # salida JSON
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import psycopg2


# ---------------------------------------------------------------------------
# Patrones de color
# ---------------------------------------------------------------------------

# Colores base + variantes género/número.  Se buscan como palabras completas
# (word-boundary) para no confundir "marino" con "submarino".
_COLOR_TOKENS: list[str] = [
    # Negro
    "Negro", "Negra", "Negros", "Negras",
    # Blanco
    "Blanco", "Blanca", "Blancos", "Blancas",
    # Gris
    "Gris", "Grises",
    # Azul
    "Azul", "Azules",
    # Marino
    "Marino", "Marina", "Marinos", "Marinas",
    # Celeste
    "Celeste", "Celestes",
    # Rojo
    "Rojo", "Roja", "Rojos", "Rojas",
    # Verde
    "Verde", "Verdes",
    # Olivo / Oliva
    "Olivo", "Oliva", "Olivos", "Olivas",
    # Amarillo
    "Amarillo", "Amarilla", "Amarillos", "Amarillas",
    # Beige
    "Beige",
    # Café
    "Café", "Cafe",
    # Camel
    "Camel",
    # Khaki / Caqui
    "Khaki", "Caqui",
    # Rosa / Rosado
    "Rosa", "Rosas", "Rosado", "Rosada", "Rosados", "Rosadas",
    # Morado
    "Morado", "Morada", "Morados", "Moradas",
    # Naranja
    "Naranja", "Naranjas",
    # Vino
    "Vino",
    # Plateado
    "Plateado", "Plateada", "Plateados", "Plateadas",
    # Dorado
    "Dorado", "Dorada", "Dorados", "Doradas",
    # Multicolor
    "Multicolor",
]

# Compilar regex que hace match de palabra completa, case-sensitive
_COLOR_RE = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in _COLOR_TOKENS) + r")\b"
)

# Valores que significan "sin color asignado" — tratados como equivalentes
_PLACEHOLDER_COLORS = {"Sin color", "Ad hoc"}

SIN_COLOR = "Sin color"


def colores_en_nombre(nombre: str) -> list[str]:
    """Devuelve los tokens de color encontrados en el nombre, en orden de aparición."""
    return _COLOR_RE.findall(nombre)


# ---------------------------------------------------------------------------
# Conexión DB
# ---------------------------------------------------------------------------

def _get_connection():
    env_path = Path(__file__).resolve().parent.parent / "pos_uniformes.env"
    env: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                env[k] = v
    return psycopg2.connect(
        host=env.get("POS_UNIFORMES_DB_HOST", "localhost"),
        port=int(env.get("POS_UNIFORMES_DB_PORT", "5432")),
        dbname=env.get("POS_UNIFORMES_DB_NAME", "pos_uniformes"),
        user=env.get("POS_UNIFORMES_DB_USER", "postgres"),
        password=env.get("POS_UNIFORMES_DB_PASSWORD", "1234"),
    )


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------

_QUERY = """
SELECT
    p.id            AS producto_id,
    p.nombre_base,
    v.id            AS variante_id,
    v.sku,
    v.color,
    v.talla
FROM producto p
LEFT JOIN variante v ON v.producto_id = p.id AND v.activo = true
WHERE p.activo = true
ORDER BY p.id, v.id;
"""


def _fetch_products(conn) -> dict[int, dict]:
    """Agrupa las filas por producto. Retorna dict keyed by producto_id."""
    cur = conn.cursor()
    cur.execute(_QUERY)
    rows = cur.fetchall()
    cur.close()

    products: dict[int, dict] = {}
    for producto_id, nombre_base, variante_id, sku, color, talla in rows:
        if producto_id not in products:
            products[producto_id] = {
                "id": producto_id,
                "nombre_base": nombre_base,
                "variantes": [],
            }
        if variante_id is not None:
            products[producto_id]["variantes"].append({
                "id": variante_id,
                "sku": sku,
                "color": color or SIN_COLOR,
                "talla": talla or "Unitalla",
            })
    return products


# ---------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------

@staticmethod  # type: ignore[misc]
def _noop(): ...  # pyflakes workaround


def audit(products: dict[int, dict]) -> dict[str, list[dict]]:
    """Analiza productos y retorna hallazgos por categoría."""
    hallazgos: dict[str, list[dict]] = defaultdict(list)

    for prod in products.values():
        nombre = prod["nombre_base"]
        variantes = prod["variantes"]
        pid = prod["id"]

        colores_nombre = colores_en_nombre(nombre)

        # ── Producto sin variantes activas ────────────────────────────────
        if not variantes:
            hallazgos["sin_variantes"].append({
                "producto_id": pid,
                "nombre_base": nombre,
            })
            continue

        colores_variantes = {v["color"] for v in variantes}
        placeholders_presentes = colores_variantes & _PLACEHOLDER_COLORS
        colores_reales = colores_variantes - _PLACEHOLDER_COLORS
        todas_placeholder = colores_reales == set()

        # ── 1. Color en nombre pero todas las variantes son placeholder ───
        if colores_nombre and todas_placeholder:
            hallazgos["color_en_nombre_sin_color_en_variante"].append({
                "producto_id": pid,
                "nombre_base": nombre,
                "colores_detectados": colores_nombre,
                "variantes": [f"{v['sku']} ({v['talla']})" for v in variantes],
            })

        # ── 2. Color en nombre Y en variante (redundancia) ────────────────
        if colores_nombre and colores_reales:
            hallazgos["color_duplicado_en_nombre_y_variante"].append({
                "producto_id": pid,
                "nombre_base": nombre,
                "colores_en_nombre": colores_nombre,
                "colores_en_variantes": sorted(colores_reales),
                "skus": [v["sku"] for v in variantes],
            })

        # ── 3. Mezcla: placeholder + color real ───────────────────────────
        if placeholders_presentes and colores_reales:
            placeholders_v = [
                f"{v['sku']} ({v['talla']}) → {v['color']}"
                for v in variantes if v["color"] in _PLACEHOLDER_COLORS
            ]
            reales_v = [
                f"{v['sku']} ({v['talla']}) → {v['color']}"
                for v in variantes if v["color"] not in _PLACEHOLDER_COLORS
            ]
            hallazgos["mezcla_sin_color_y_con_color"].append({
                "producto_id": pid,
                "nombre_base": nombre,
                "variantes_sin_color": placeholders_v,
                "variantes_con_color": reales_v,
            })

        # ── 4. Mezcla de placeholders distintos (ej: 'Ad hoc' + 'Sin color') ─
        if len(placeholders_presentes) > 1:
            hallazgos["mezcla_placeholders_color"].append({
                "producto_id": pid,
                "nombre_base": nombre,
                "placeholders": sorted(placeholders_presentes),
                "detalle": [
                    f"{v['sku']} talla={v['talla']} color={v['color']}"
                    for v in variantes if v["color"] in _PLACEHOLDER_COLORS
                ],
            })

    return dict(hallazgos)


# ---------------------------------------------------------------------------
# Reporte en texto
# ---------------------------------------------------------------------------

_SEPARADOR = "─" * 70


def _plural(n: int, sing: str, plur: str) -> str:
    return f"{n} {sing if n == 1 else plur}"


def _imprimir_reporte(hallazgos: dict[str, list[dict]]) -> None:
    total = sum(len(v) for v in hallazgos.values())

    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║          AUDITORÍA DE INCONSISTENCIAS — CATÁLOGO POS UNIFORMES       ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print()

    if total == 0:
        print("  ✅  Sin inconsistencias encontradas.")
        print()
        return

    print(f"  {_plural(total, 'inconsistencia encontrada', 'inconsistencias encontradas')}")
    print()

    # ── Sección 1 ─────────────────────────────────────────────────────────
    items = hallazgos.get("color_en_nombre_sin_color_en_variante", [])
    if items:
        print(_SEPARADOR)
        print(f"  ⚠️  COLOR EN NOMBRE PERO «Sin color» EN VARIANTES  ({len(items)})")
        print(f"     El nombre describe un color pero las variantes no tienen color asignado.")
        print(_SEPARADOR)
        for i in items:
            print(f"  ID {i['producto_id']:>5}  {i['nombre_base']}")
            print(f"          Colores detectados: {', '.join(i['colores_detectados'])}")
            print(f"          Variantes: {', '.join(i['variantes'][:5])}"
                  + (f"  …+{len(i['variantes'])-5}" if len(i['variantes']) > 5 else ""))
            print()

    # ── Sección 2 ─────────────────────────────────────────────────────────
    items = hallazgos.get("color_duplicado_en_nombre_y_variante", [])
    if items:
        print(_SEPARADOR)
        print(f"  ℹ️   COLOR DUPLICADO: ESTÁ EN NOMBRE Y EN VARIANTE  ({len(items)})")
        print(f"     El nombre_base incluye el color pero las variantes también lo tienen.")
        print(f"     Considera usar un nombre_base neutro (sin color).")
        print(_SEPARADOR)
        for i in items:
            print(f"  ID {i['producto_id']:>5}  {i['nombre_base']}")
            print(f"          En nombre: {', '.join(i['colores_en_nombre'])}")
            print(f"          En variantes: {', '.join(i['colores_en_variantes'])}")
            print()

    # ── Sección 3 ─────────────────────────────────────────────────────────
    items = hallazgos.get("mezcla_sin_color_y_con_color", [])
    if items:
        print(_SEPARADOR)
        print(f"  ⚠️  MEZCLA: ALGUNAS VARIANTES «Sin color» Y OTRAS CON COLOR  ({len(items)})")
        print(f"     Posible entrada incompleta: no todas las variantes tienen color asignado.")
        print(_SEPARADOR)
        for i in items:
            print(f"  ID {i['producto_id']:>5}  {i['nombre_base']}")
            print(f"          Sin color: {', '.join(i['variantes_sin_color'][:3])}"
                  + (f"  …+{len(i['variantes_sin_color'])-3}" if len(i['variantes_sin_color']) > 3 else ""))
            print(f"          Con color: {', '.join(i['variantes_con_color'][:3])}"
                  + (f"  …+{len(i['variantes_con_color'])-3}" if len(i['variantes_con_color']) > 3 else ""))
            print()

    # ── Sección 4 ─────────────────────────────────────────────────────────
    items = hallazgos.get("mezcla_placeholders_color", [])
    if items:
        print(_SEPARADOR)
        print(f"  ⚠️  MEZCLA DE PLACEHOLDERS DE COLOR (ej: 'Ad hoc' + 'Sin color')  ({len(items)})")
        print(f"     Distintos valores de 'sin color' usados en la misma variante.")
        print(_SEPARADOR)
        for i in items:
            print(f"  ID {i['producto_id']:>5}  {i['nombre_base']}")
            print(f"          Placeholders: {', '.join(i['placeholders'])}")
            print(f"          Detalle: {', '.join(i['detalle'][:4])}"
                  + (f"  …+{len(i['detalle'])-4}" if len(i['detalle']) > 4 else ""))
            print()

    # ── Sección 5 ─────────────────────────────────────────────────────────
    items = hallazgos.get("sin_variantes", [])
    if items:
        print(_SEPARADOR)
        print(f"  🔴  PRODUCTOS ACTIVOS SIN VARIANTES ACTIVAS  ({len(items)})")
        print(_SEPARADOR)
        for i in items:
            print(f"  ID {i['producto_id']:>5}  {i['nombre_base']}")
        print()

    print(_SEPARADOR)
    print(f"  Total: {_plural(total, 'registro', 'registros')} a revisar.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Auditor de inconsistencias en catálogo.")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON.")
    args = parser.parse_args()

    try:
        conn = _get_connection()
    except Exception as exc:
        print(f"❌  No se pudo conectar a la base de datos: {exc}", file=sys.stderr)
        return 1

    try:
        products = _fetch_products(conn)
    finally:
        conn.close()

    hallazgos = audit(products)

    if args.json:
        print(json.dumps(hallazgos, ensure_ascii=False, indent=2))
    else:
        _imprimir_reporte(hallazgos)

    # Exit code 1 si hay inconsistencias críticas (categorías 1 y 3)
    criticos = (
        len(hallazgos.get("color_en_nombre_sin_color_en_variante", []))
        + len(hallazgos.get("mezcla_sin_color_y_con_color", []))
        + len(hallazgos.get("mezcla_placeholders_color", []))
    )
    return 1 if criticos > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
