#!/usr/bin/env python3
"""Parser de lenguaje natural para generar presupuestos de uniformes.

Interpreta frases como:
  "oficial completo niña Margarita Paz talla 8"
  "deportivo completo Emiliano Zapata talla 10"
  "completo niño CBTIS 148 talla 32"
  "suéter y pantalón Frida Kahlo talla 6"

Uso standalone:
    python3 scripts/presupuesto_parser.py

Uso como módulo:
    from presupuesto_parser import parse_request, generate_quote
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import psycopg2


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

def _get_connection():
    env_path = Path(__file__).resolve().parent.parent / "pos_uniformes.env"
    env = {}
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
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ParsedRequest:
    escuela: Optional[str] = None
    escuela_id: Optional[int] = None
    tipo_uniforme: Optional[str] = None  # 'oficial', 'deportivo', None=ambos
    completo: bool = False
    genero: Optional[str] = None  # 'Hombre', 'Mujer', None
    tallas: list[str] = field(default_factory=list)
    cantidad: int = 1
    piezas_especificas: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    needs_gender: bool = False


@dataclass
class QuoteLine:
    tipo_pieza: str
    producto: str
    genero: str
    talla: str
    precio: float
    tipo_uniforme: str


@dataclass
class QuoteResult:
    escuela: str
    tipo_uniforme: str
    genero: str
    tallas: list[str]
    lines: list[QuoteLine] = field(default_factory=list)
    total: float = 0.0


# ---------------------------------------------------------------------------
# School fuzzy matching
# ---------------------------------------------------------------------------

_SCHOOL_ALIASES = {
    "margarita": "Margarita Paz Paredes",
    "margarita paz": "Margarita Paz Paredes",
    "blanca": "Blanca Verónica Soto Martínez Príncipes",
    "blanca veronica": "Blanca Verónica Soto Martínez Príncipes",
    "cbtis": "CBTIS 148",
    "cecyte": "CECYTE",
    "sabes": "SABES",
    "uveg": "UVEG",
    "conalep": "Conalep",
    "motolinea": "Colegio Motolinea",
    "frida": "Frida Kahlo",
    "frida kahlo": "Frida Kahlo",
    "piaget": "Jean Piaget",
    "jean piaget": "Jean Piaget",
    "cantor": "Jorge Cantor",
    "jorge cantor": "Jorge Cantor",
    "patria": "Patria",
    "alvaro": "Álvaro Obregón",
    "alvaro obregon": "Álvaro Obregón",
    "bicentenario": "Bicentenario",
    "sor juana": "Sor Juana Inés de la Cruz",
    "emiliano": "Emiliano Zapata",
    "emiliano zapata": "Emiliano Zapata",
    "himno": "Himno Nacional",
    "himno nacional": "Himno Nacional",
    "guadalupe victoria": "J. Guadalupe Victoria",
    "morelos": "José María Morelos",
    "jose maria morelos": "José María Morelos",
    "morelos y pavon": "José María Morelos y Pavón",
    "justo sierra": "Justo Sierra",
    "niños heroes": "Niños Héroes",
    "praxedis": "Práxedis Guerrero",
    "praxedis guerrero": "Práxedis Guerrero",
    "campuzano": "Miguel Campuzano",
    "miguel hidalgo": "Miguel Hidalgo",
    "ninos heroes hidalgo": "Niños Héroes de Miguel Hidalgo",
    "ignacio ramirez": "Ignacio Ramirez Lopez",
    "zaragoza": "Ignacio Zaragoza",
    "ignacio zaragoza": "Ignacio Zaragoza",
    "vicente guerrero": "Vicente Guerrero",
    "narciso": "Narciso Mendoza",
    "narciso mendoza": "Narciso Mendoza",
    "adolfo lopez": "Adolfo Lopez Mateo",
    "huizache": "Huizache",
    "palacio": "Palacio",
    "club rotario": "Club Rotario",
    "francisco villa": "Francisco Villa",
    "albino": "Albino García Ramos",
    "benito juarez": "Lic. Benito Juárez",
    "santa rosa": "Santa Rosa 238",
    "vidal": "Vidal Alcocer",
    "tele 454": "Telesecundaria 454",
    "tele 512": "Telesecundaria 512",
    "tele 600": "Telesecundaria 600",
    "telesecundaria 454": "Telesecundaria 454",
    "telesecundaria 512": "Telesecundaria 512",
    "telesecundaria 600": "Telesecundaria 600",
    "tecnica": "Técnica de San Bartolo",
    "estv 154": "ESTV 154",
    "estv 663": "ESTV 663",
    "ignacio allende": "Ignacio Allende",
    "allende": "Ignacio Allende",
}

# Gender keywords
_GENDER_FEMALE = {"niña", "niñas", "nina", "ninas", "mujer", "mujeres", "hija", "nena"}
_GENDER_MALE = {"niño", "niños", "nino", "ninos", "hombre", "hombres", "hijo", "nene"}

# Tipo uniforme keywords
_TIPO_OFICIAL = {"oficial", "gala", "diario", "vestir"}
_TIPO_DEPORTIVO = {"deportivo", "deporte", "sport"}

# Pieza keywords
_PIEZA_KEYWORDS = {
    "pants": "Pants", "pants 3pz": "Pants 3pz", "pants 2pz": "Pants 2pz",
    "pants suelto": "Pants Suelto", "chamarra": "Chamarra", "playera": "Playera",
    "sueter": "Suéter", "suéter": "Suéter", "falda": "Falda",
    "camisa": "Camisa", "chaleco": "Chaleco", "pantalon": "Pantalón",
    "pantalón": "Pantalón", "corbata": "Corbata", "corbatin": "Corbatín",
    "corbatín": "Corbatín", "moño": "Moño", "mono": "Moño",
    "mascada": "Mascada", "jumper": "Jumper", "blusa": "Blusa",
    "boina": "Boina", "bata": "Bata", "calceta": "Calceta",
    "malla": "Malla",
}


def _normalize(text: str) -> str:
    """Lowercase, strip accents for matching."""
    import unicodedata
    text = text.lower().strip()
    # Keep original for accent-sensitive matching but also create a normalized version
    return text


def _fuzzy_match_school(query: str, school_names: list[str]) -> tuple[Optional[str], float]:
    """Find best matching school name using fuzzy matching."""
    query_lower = query.lower().strip()

    # 1. Check aliases first (exact)
    if query_lower in _SCHOOL_ALIASES:
        return _SCHOOL_ALIASES[query_lower], 1.0

    # 2. Check aliases (partial)
    for alias, name in sorted(_SCHOOL_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in query_lower:
            return name, 0.95

    # 3. Fuzzy match against DB names
    best_name = None
    best_score = 0.0
    for name in school_names:
        score = SequenceMatcher(None, query_lower, name.lower()).ratio()
        if score > best_score:
            best_score = score
            best_name = name

        # Also check if query is a substring
        if query_lower in name.lower():
            return name, 0.9

    if best_score >= 0.55:
        return best_name, best_score

    return None, 0.0


def _extract_tallas(text: str) -> list[str]:
    """Extract talla values from text."""
    tallas = []

    # Pattern: "talla 8" or "tallas 8, 10, 12" or "talla 8 y 10"
    m = re.search(r'tallas?\s+([\d\w,\syY]+)', text, re.IGNORECASE)
    if m:
        raw = m.group(1)
        # Split by comma, "y", spaces
        parts = re.split(r'[,\s]+y\s+|[,\s]+', raw)
        for p in parts:
            p = p.strip()
            if p and (p.isdigit() or p.upper() in (
                'CH', 'MD', 'M', 'GD', 'G', 'XCH', 'EXG', 'XL', '2XL', '3XL',
                'U', 'UNITALLA',
            )):
                tallas.append(p.upper() if not p.isdigit() else p)
        return tallas

    # Fallback: standalone numbers that look like tallas (2-44, even)
    # Only if no other talla pattern found
    return tallas


def _extract_cantidad(text: str) -> int:
    """Extract quantity from text."""
    m = re.search(r'(\d+)\s*(niñ[oa]s?|niñ[oa]s?|hij[oa]s?|uniform)', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 1


def _extract_piezas(text: str) -> list[str]:
    """Extract specific piece names from text."""
    piezas = []
    text_lower = text.lower()

    # Check multi-word pieces first (longer matches first)
    for kw, pieza in sorted(_PIEZA_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in text_lower:
            if pieza not in piezas:
                piezas.append(pieza)
            # Remove from text to avoid double matches
            text_lower = text_lower.replace(kw, " ")

    return piezas


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_request(text: str, school_names: list[str]) -> ParsedRequest:
    """Parse a natural language uniform quote request."""
    req = ParsedRequest()
    text_lower = text.lower().strip()

    # 1. Tipo uniforme
    for kw in _TIPO_OFICIAL:
        if kw in text_lower:
            req.tipo_uniforme = "oficial"
            break
    for kw in _TIPO_DEPORTIVO:
        if kw in text_lower:
            req.tipo_uniforme = "deportivo"
            break

    # 2. Completo
    if "completo" in text_lower or "completa" in text_lower or "todo" in text_lower:
        req.completo = True

    # 3. Género
    words = set(re.findall(r'\w+', text_lower))
    if words & _GENDER_FEMALE:
        req.genero = "Mujer"
    elif words & _GENDER_MALE:
        req.genero = "Hombre"

    # 4. Tallas
    req.tallas = _extract_tallas(text)

    # 5. Cantidad
    req.cantidad = _extract_cantidad(text)

    # 6. Piezas específicas (only if not "completo")
    if not req.completo:
        req.piezas_especificas = _extract_piezas(text)

    # 7. Escuela — remove known keywords first, then fuzzy match remainder
    school_text = text_lower
    for remove in (
        list(_TIPO_OFICIAL) + list(_TIPO_DEPORTIVO) +
        list(_GENDER_FEMALE) + list(_GENDER_MALE) +
        ["completo", "completa", "todo", "talla", "tallas", "precio", "presupuesto",
         "uniforme", "dame", "dime", "quiero", "necesito", "cuanto", "cuánto",
         "cuesta", "el", "la", "los", "las", "de", "del", "para", "un", "una", "y"]
    ):
        school_text = re.sub(r'\b' + re.escape(remove) + r'\b', ' ', school_text)
    # Remove numbers and extra spaces
    school_text = re.sub(r'\b\d+\b', ' ', school_text)
    school_text = re.sub(r'\s+', ' ', school_text).strip()

    # Remove pieza keywords from school search
    for kw in _PIEZA_KEYWORDS:
        school_text = re.sub(r'\b' + re.escape(kw) + r'\b', ' ', school_text)
    school_text = re.sub(r'\s+', ' ', school_text).strip()

    if school_text:
        match, score = _fuzzy_match_school(school_text, school_names)
        if match:
            req.escuela = match
        else:
            req.errors.append(f"No encontré la escuela '{school_text}'")

    # 8. Check if gender is needed for oficial completo
    if req.completo and req.tipo_uniforme in ("oficial", None) and req.genero is None:
        req.needs_gender = True

    # Validation
    if not req.escuela:
        req.errors.append("No detecté el nombre de la escuela")
    if not req.tallas:
        req.errors.append("No detecté la talla")

    return req


# ---------------------------------------------------------------------------
# Quote generation
# ---------------------------------------------------------------------------

def generate_quote(req: ParsedRequest, conn) -> QuoteResult:
    """Generate a quote from a parsed request."""
    cur = conn.cursor()

    # Get escuela_id
    cur.execute("SELECT id FROM escuela WHERE nombre = %s AND activo = true", (req.escuela,))
    row = cur.fetchone()
    if not row:
        return QuoteResult(
            escuela=req.escuela or "?", tipo_uniforme=req.tipo_uniforme or "completo",
            genero=req.genero or "?", tallas=req.tallas,
        )
    escuela_id = row[0]
    req.escuela_id = escuela_id

    # Build query
    conditions = ["v.activo = true"]
    params: list = []

    # Gender filter
    if req.genero:
        conditions.append("sp.genero IN (%s, 'Unisex')")
        params.append(req.genero)
    # else: no gender filter, show all

    # Tipo uniforme filter
    if req.tipo_uniforme:
        conditions.append("tp.tipo_uniforme = %s")
        params.append(req.tipo_uniforme)

    # Completo: deportivo = solo Pants 3pz, sin tipo = Pants 3pz + todo oficial
    if req.completo and req.tipo_uniforme == "deportivo":
        conditions.append("tp.nombre = 'Pants 3pz'")
    elif req.completo and req.tipo_uniforme is None:
        # Completo sin especificar = Pants 3pz (deportivo) + todo oficial
        conditions.append("(tp.nombre = 'Pants 3pz' OR tp.tipo_uniforme = 'oficial')")
    elif not req.completo and req.piezas_especificas:
        placeholders = ", ".join(["%s"] * len(req.piezas_especificas))
        conditions.append(f"tp.nombre IN ({placeholders})")
        params.extend(req.piezas_especificas)

    # Tallas
    if req.tallas:
        placeholders = ", ".join(["%s"] * len(req.tallas))
        conditions.append(f"v.talla IN ({placeholders})")
        params.extend(req.tallas)

    where_clause = " AND ".join(conditions)

    query = f"""
        WITH school_products AS (
            SELECT p.id, p.nombre, tp.nombre AS tipo, tp.tipo_uniforme, p.genero
            FROM producto p
            JOIN tipo_pieza tp ON tp.id = p.tipo_pieza_id
            WHERE p.activo = true AND p.escuela_id = %s
            UNION
            SELECT p.id, p.nombre, tp.nombre AS tipo, tp.tipo_uniforme, p.genero
            FROM catalog_school_product_link l
            JOIN producto p ON p.id = l.producto_id AND p.activo = true
            JOIN tipo_pieza tp ON tp.id = p.tipo_pieza_id
            WHERE l.activo = true AND l.escuela_id = %s
        )
        SELECT sp.tipo, sp.nombre, sp.genero, sp.tipo_uniforme, v.talla, v.precio_venta
        FROM school_products sp
        JOIN variante v ON v.producto_id = sp.id
        JOIN tipo_pieza tp ON tp.nombre = sp.tipo
        WHERE {where_clause}
        ORDER BY
            CASE sp.tipo_uniforme WHEN 'deportivo' THEN 0 ELSE 1 END,
            sp.tipo, sp.nombre, v.talla
    """

    cur.execute(query, [escuela_id, escuela_id] + params)

    rows = cur.fetchall()

    # Post-filter: if school has olan AND request is for niña, skip manga corta
    # (olan is the girl's camisa, manga corta is Unisex but acts as boy's camisa in olan schools)
    has_olan = any("olan" in (r[1] or "").lower() for r in rows)
    if has_olan and req.genero == "Mujer":
        rows = [r for r in rows if "manga corta" not in (r[1] or "").lower()]

    result = QuoteResult(
        escuela=req.escuela,
        tipo_uniforme=req.tipo_uniforme or "completo",
        genero=req.genero or "todos",
        tallas=req.tallas,
    )

    for row in rows:
        line = QuoteLine(
            tipo_pieza=row[0], producto=row[1], genero=row[2],
            tipo_uniforme=row[3], talla=row[4], precio=float(row[5] or 0),
        )
        result.lines.append(line)
        result.total += line.precio

    result.total *= req.cantidad

    return result


# ---------------------------------------------------------------------------
# Ticket formatting
# ---------------------------------------------------------------------------

TICKET_WIDTH = 42


def _center(text: str) -> str:
    return text.center(TICKET_WIDTH)


def _sep() -> str:
    return "—" * TICKET_WIDTH


def _row(label: str, value: str) -> str:
    space = TICKET_WIDTH - len(label) - len(value)
    return f"{label}{' ' * max(space, 1)}{value}"


def format_ticket(req: ParsedRequest, result: QuoteResult) -> str:
    """Format quote as a printable ticket."""
    lines = []
    lines.append(_center("MAXIMODA"))
    lines.append(_center("Presupuesto Estimado"))
    lines.append(_sep())
    lines.append(_center("ESTE NO ES UN COMPROBANTE"))
    lines.append(_center("FISCAL NI DE COMPRA"))
    lines.append(_center("Precios solo de referencia"))
    lines.append(_sep())

    lines.append(_row("Escuela:", req.escuela or "?"))
    tipo_label = {
        "oficial": "Oficial", "deportivo": "Deportivo",
    }.get(req.tipo_uniforme, "Completo")
    lines.append(_row("Uniforme:", tipo_label))

    genero_label = {"Hombre": "Niño", "Mujer": "Niña"}.get(req.genero, "")
    if genero_label:
        lines.append(_row("Género:", genero_label))
    lines.append(_row("Talla(s):", ", ".join(req.tallas)))
    if req.cantidad > 1:
        lines.append(_row("Cantidad:", f"x{req.cantidad}"))

    lines.append(_sep())
    lines.append("PIEZAS")
    lines.append(_sep())

    if not result.lines:
        lines.append("")
        lines.append("  No se encontraron productos")
        lines.append("  para esta combinación.")
    else:
        # Group by talla
        by_talla: dict[str, list[QuoteLine]] = defaultdict(list)
        for line in result.lines:
            by_talla[line.talla].append(line)

        for talla in req.tallas:
            if talla not in by_talla:
                continue
            if len(req.tallas) > 1:
                lines.append("")
                lines.append(f"  ── Talla {talla} ──")

            talla_total = 0.0
            for ql in by_talla[talla]:
                lines.append("")
                lines.append(f"  {ql.producto}")
                lines.append(_row(f"    {ql.tipo_pieza} | {ql.talla}", f"${ql.precio:,.0f}"))
                talla_total += ql.precio

            if len(req.tallas) > 1:
                lines.append(f"  {'':30s} ────────")
                lines.append(_row(f"  Subtotal talla {talla}:", f"${talla_total:,.0f}"))

    lines.append(_sep())

    if req.cantidad > 1:
        unit_total = result.total / req.cantidad
        lines.append(_row("Subtotal (x1):", f"${unit_total:,.0f}"))
        lines.append(_row(f"TOTAL (x{req.cantidad}):", f"${result.total:,.0f}"))
    else:
        lines.append(_row("PRESUPUESTO ESTIMADO:", f"${result.total:,.0f}"))

    lines.append(_sep())
    lines.append("")
    lines.append(_center("Precios sujetos a cambio"))
    lines.append(_center("sin previo aviso"))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

def _load_schools(conn) -> list[str]:
    cur = conn.cursor()
    cur.execute("SELECT nombre FROM escuela WHERE activo = true ORDER BY nombre")
    return [r[0] for r in cur.fetchall()]


def run_interactive():
    """Run interactive CLI loop."""
    conn = _get_connection()
    school_names = _load_schools(conn)

    print("=" * TICKET_WIDTH)
    print(_center("MAXIMODA — Presupuestos"))
    print("=" * TICKET_WIDTH)
    print()
    print("Escribe tu solicitud en lenguaje natural.")
    print("Ejemplos:")
    print('  "oficial completo niña Margarita Paz talla 8"')
    print('  "deportivo completo Emiliano Zapata talla 10"')
    print('  "suéter y pantalón Frida Kahlo niño talla 6"')
    print()
    print("Escribe 'salir' para terminar.")
    print()

    while True:
        try:
            text = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break

        if not text:
            continue
        if text.lower() in ("salir", "exit", "quit", "q"):
            print("Hasta luego.")
            break

        req = parse_request(text, school_names)

        # Ask for missing info
        if req.needs_gender and not req.genero:
            try:
                g = input("  ¿Niño o niña? ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                continue
            if g in _GENDER_FEMALE or g == "niña":
                req.genero = "Mujer"
            elif g in _GENDER_MALE or g == "niño":
                req.genero = "Hombre"
            req.needs_gender = False

        if req.errors:
            for e in req.errors:
                print(f"  ⚠️  {e}")
            if not req.escuela or not req.tallas:
                continue

        # Show what was understood
        print()
        print(f"  Escuela:  {req.escuela}")
        print(f"  Tipo:     {req.tipo_uniforme or 'completo (deportivo + oficial)'}")
        _gl = {'Hombre': 'Niño', 'Mujer': 'Niña'}.get(req.genero, 'todos')
        print(f"  Género:   {_gl}")
        print(f"  Talla(s): {', '.join(req.tallas)}")
        if req.piezas_especificas:
            print(f"  Piezas:   {', '.join(req.piezas_especificas)}")
        print()

        result = generate_quote(req, conn)

        if not result.lines:
            print("  No se encontraron productos para esta combinación.")
            print()
            continue

        ticket = format_ticket(req, result)
        print()
        print(ticket)
        print()

    conn.close()


if __name__ == "__main__":
    run_interactive()
