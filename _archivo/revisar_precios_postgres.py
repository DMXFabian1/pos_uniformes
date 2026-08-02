"""
Revisa precios en PostgreSQL contra reglas_precios_v1.md
Reporta variantes cuyo precio_venta < precio_objetivo (incumple MAX rule).
"""
from __future__ import annotations
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from decimal import Decimal
from dataclasses import dataclass
import sqlalchemy as sa

DB_URL = "postgresql+psycopg://postgres:1234@localhost:5432/pos_uniformes"

# ---------------------------------------------------------------------------
# Reglas: (filtro_fn, precio_objetivo)
# filtro_fn recibe una fila con columnas:
#   sku, talla, precio_venta, nombre_prod, nombre_base,
#   tipo_pieza, tipo_prenda, nivel_educativo, atributo, escudo, escuela_id
# ---------------------------------------------------------------------------

def _talla(row, *tallas):
    return row.talla in tallas

def _tallas(row, lst):
    return row.talla in lst

TALLAS_INF  = {"2","4","6","8","10"}
TALLAS_JUV  = {"12","14","16","18"}
TALLAS_ADU  = {"30","32","34","36","38","40","42","44","CH","MD","GD","EXG"}

@dataclass
class Regla:
    descripcion: str
    precio_objetivo: int

    def aplica(self, row) -> bool:
        raise NotImplementedError

    def chequear(self, row) -> tuple[bool, int] | None:
        """Retorna (incumple, objetivo) o None si no aplica."""
        if self.aplica(row):
            if row.precio_venta < self.precio_objetivo:
                return (True, self.precio_objetivo)
            return (False, self.precio_objetivo)
        return None


# ── helpers ────────────────────────────────────────────────────────────────

def _nombre_contiene(row, *frags):
    n = (row.nombre_prod or "").lower()
    return all(f.lower() in n for f in frags)

def _nombre_base_contiene(row, *frags):
    n = (row.nombre_base or "").lower()
    return all(f.lower() in n for f in frags)


# ── 1. Playeras ─────────────────────────────────────────────────────────────

REGLAS_PLAYERAS: list[Regla] = []

class _PlayeraRegla(Regla):
    def __init__(self, nivel, tallas, precio):
        super().__init__(f"Playera {nivel} tallas {tallas}", precio)
        self._nivel = nivel
        self._tallas = set(tallas)
    def aplica(self, r):
        return (
            r.tipo_pieza == "Playera"
            and r.nivel_educativo == self._nivel
            and r.talla in self._tallas
        )

for _nivel, _grupos in [
    ("Preescolar", [
        (["2","4","6","8","10"], 175),
        (["12","14","16"], 199),
        (["CH","MD","GD","EXG"], 219),
    ]),
    ("Primaria", [
        (["4","6","8","10"], 199),
        (["12","14","16"], 209),
        (["CH","MD","GD","EXG"], 219),
    ]),
    ("Secundaria", [
        (["12","14","16"], 229),
        (["CH","MD","GD","EXG"], 239),
    ]),
    ("Bachillerato", [
        (["12","14","16"], 229),
        (["CH","MD","GD","EXG"], 239),
    ]),
]:
    for _tallas, _precio in _grupos:
        REGLAS_PLAYERAS.append(_PlayeraRegla(_nivel, _tallas, _precio))


# ── 2. Suéter Básico ─────────────────────────────────────────────────────────

class _SueterBasicoRegla(Regla):
    def __init__(self, tallas, precio):
        super().__init__(f"Suéter Básico tallas {tallas}", precio)
        self._tallas = set(tallas)
    def aplica(self, r):
        return (
            r.tipo_pieza == "Suéter"
            and r.tipo_prenda == "Básico"
            and "oferta ad hoc" not in (r.nombre_prod or "").lower()
            and r.talla in self._tallas
        )

REGLAS_SUETER_BASICO = [
    _SueterBasicoRegla(["4","6","8"], 289),
    _SueterBasicoRegla(["10","12","14","16"], 299),
    _SueterBasicoRegla(["30","32","34"], 309),
    _SueterBasicoRegla(["36","38","40","42"], 315),
    _SueterBasicoRegla(["44","46"], 325),
]


# ── 3. Suéter Oficial ────────────────────────────────────────────────────────

class _SueterOficialRegla(Regla):
    def __init__(self, nivel, tallas, precio, escuela_override=None):
        super().__init__(f"Suéter Oficial {nivel} {tallas}", precio)
        self._nivel = nivel
        self._tallas = set(tallas)
        self._escuela = escuela_override  # nombre parcial
    def aplica(self, r):
        if r.tipo_pieza != "Suéter" or r.tipo_prenda != "Oficial":
            return False
        if r.nivel_educativo != self._nivel:
            return False
        if self._escuela:
            return (
                self._escuela.lower() in (r.nombre_prod or "").lower()
                and r.talla in self._tallas
            )
        return r.talla in self._tallas

REGLAS_SUETER_OFICIAL = [
    _SueterOficialRegla("Preescolar", ["4","6","8","10"], 290),
    _SueterOficialRegla("Primaria",   ["4","6","8","10"], 290),
    _SueterOficialRegla("Primaria",   ["12","14","16"], 315),
    _SueterOficialRegla("Primaria",   ["30","32","34","36","38","40","42"], 325),
    _SueterOficialRegla("Secundaria", ["12","14","16"], 325),
    _SueterOficialRegla("Secundaria", ["30","32","34","36","38","40","42","44"], 345),
    _SueterOficialRegla("Bachillerato", ["14","16"], 325),
    _SueterOficialRegla("Bachillerato", ["32","34"], 335),
    _SueterOficialRegla("Bachillerato", ["36","38"], 345),
    _SueterOficialRegla("Bachillerato", ["40","42","44"], 355),
    # UVEG excepción
    _SueterOficialRegla("Bachillerato", ["14","16","32","34","36","38","40","42"], 355, "UVEG"),
]


# ── 4. Camisas Básicas ───────────────────────────────────────────────────────

class _CamisaBasicaRegla(Regla):
    def __init__(self, familia_frag, tallas, precio):
        super().__init__(f"Camisa Básica '{familia_frag}' {tallas}", precio)
        self._frag = familia_frag.lower()
        self._tallas = set(tallas)
    def aplica(self, r):
        return (
            r.tipo_pieza == "Camisa"
            and r.tipo_prenda == "Básico"
            and self._frag in (r.nombre_prod or "").lower()
            and r.talla in self._tallas
        )

REGLAS_CAMISA_BASICA = [
    # Manga Corta Blanca (sin Prowear)
    _CamisaBasicaRegla("manga corta blanca", ["4","6","8"], 89),
    _CamisaBasicaRegla("manga corta blanca", ["10","12","14","16"], 99),
    _CamisaBasicaRegla("manga corta blanca", ["28","30"], 115),
    _CamisaBasicaRegla("manga corta blanca", ["32","34"], 135),
    _CamisaBasicaRegla("manga corta blanca", ["36","38"], 145),
    _CamisaBasicaRegla("manga corta blanca", ["40","42"], 165),
    # Prowear
    _CamisaBasicaRegla("prowear manga corta blanca", ["4","6","8"], 125),
    _CamisaBasicaRegla("prowear manga corta blanca", ["10","12"], 145),
    _CamisaBasicaRegla("prowear manga corta blanca", ["14","16"], 155),
    _CamisaBasicaRegla("prowear manga corta blanca", ["28","30","32","34","36","38"], 165),
    _CamisaBasicaRegla("prowear manga corta blanca", ["40","42"], 185),
    # Manga Larga H
    _CamisaBasicaRegla("manga larga h blanca", ["2","4","6","8"], 199),
    _CamisaBasicaRegla("manga larga h blanca", ["10","12","14","16","18"], 219),
    _CamisaBasicaRegla("manga larga h blanca", ["32","34"], 239),
    _CamisaBasicaRegla("manga larga h blanca", ["36","38"], 249),
    _CamisaBasicaRegla("manga larga h blanca", ["40","42","44","CH"], 259),
    _CamisaBasicaRegla("manga larga h blanca", ["MD"], 269),
    _CamisaBasicaRegla("manga larga h blanca", ["GD"], 279),
    _CamisaBasicaRegla("manga larga h blanca", ["EXG"], 289),
    # Manga Larga M
    _CamisaBasicaRegla("manga larga m blanca", ["30","CH"], 269),
    _CamisaBasicaRegla("manga larga m blanca", ["MD","GD"], 289),
    _CamisaBasicaRegla("manga larga m blanca", ["EXG"], 309),
]

# Camisas Oficiales
class _CamisaOficialRegla(Regla):
    def __init__(self, nivel, tallas, precio):
        super().__init__(f"Camisa Oficial {nivel} {tallas}", precio)
        self._nivel = nivel
        self._tallas = set(tallas) if tallas != "linea_completa" else None
    def aplica(self, r):
        return (
            r.tipo_pieza == "Camisa"
            and r.tipo_prenda == "Oficial"
            and r.nivel_educativo == self._nivel
            and (self._tallas is None or r.talla in self._tallas)
        )

REGLAS_CAMISA_OFICIAL = [
    _CamisaOficialRegla("Preescolar", "linea_completa", 139),
    _CamisaOficialRegla("Primaria",   ["4","6","8","10"], 215),
    _CamisaOficialRegla("Primaria",   ["12","14","16"], 225),
    _CamisaOficialRegla("Primaria",   ["32","34","36","38"], 245),
    _CamisaOficialRegla("Secundaria", "linea_completa", 265),
    _CamisaOficialRegla("Bachillerato", "linea_completa", 265),
]


# ── 5. Chalecos ──────────────────────────────────────────────────────────────

class _ChalecoBasicoRegla(Regla):
    def __init__(self, tallas, precio):
        super().__init__(f"Chaleco Básico {tallas}", precio)
        self._tallas = set(tallas)
    def aplica(self, r):
        return r.tipo_pieza == "Chaleco" and r.tipo_prenda == "Básico" and r.talla in self._tallas

REGLAS_CHALECO_BASICO = [
    _ChalecoBasicoRegla(["4","6","8"], 229),
    _ChalecoBasicoRegla(["10","12","14","16"], 239),
    _ChalecoBasicoRegla(["28","30","32","34"], 259),
    _ChalecoBasicoRegla(["36","38","40","42","44","46"], 269),
]

class _ChalecoOficialRegla(Regla):
    def __init__(self, nivel, tallas, precio):
        super().__init__(f"Chaleco Oficial {nivel} {tallas}", precio)
        self._nivel = nivel
        self._tallas = set(tallas)
    def aplica(self, r):
        return (
            r.tipo_pieza == "Chaleco"
            and r.tipo_prenda == "Oficial"
            and r.nivel_educativo == self._nivel
            and r.talla in self._tallas
        )

REGLAS_CHALECO_OFICIAL = [
    _ChalecoOficialRegla("Primaria", ["2","4","6","8"], 240),
    _ChalecoOficialRegla("Primaria", ["10","12"], 250),
    _ChalecoOficialRegla("Primaria", ["14","16"], 260),
    _ChalecoOficialRegla("Primaria", ["32"], 270),
    _ChalecoOficialRegla("Primaria", ["34","36"], 290),
    _ChalecoOficialRegla("Primaria", ["38","40"], 300),
    _ChalecoOficialRegla("Primaria", ["42","CH","MD","GD","EXG"], 290),
    _ChalecoOficialRegla("Secundaria", ["12","14","16"], 245),
    _ChalecoOficialRegla("Secundaria", ["30","32","34"], 265),
    _ChalecoOficialRegla("Secundaria", ["36","38","40","42","44"], 275),
    _ChalecoOficialRegla("Bachillerato", ["14","16"], 265),
    _ChalecoOficialRegla("Bachillerato", ["32","34"], 275),
    _ChalecoOficialRegla("Bachillerato", ["36","38","40","42"], 285),
    _ChalecoOficialRegla("Bachillerato", ["44"], 295),
]


# ── 6. Faldas ────────────────────────────────────────────────────────────────

class _FaldaBasicaRegla(Regla):
    def __init__(self, familia_frags, tallas, precio):
        super().__init__(f"Falda Básica {familia_frags} {tallas}", precio)
        self._frags = [f.lower() for f in familia_frags]
        self._tallas = set(tallas)
    def aplica(self, r):
        if r.tipo_pieza != "Falda" or r.tipo_prenda != "Básico":
            return False
        nombre = (r.nombre_prod or "").lower()
        return any(f in nombre for f in self._frags) and r.talla in self._tallas

_FALDAS_ESTANDAR_FRAGS = [
    "falda escolar azul marino", "falda gales azul", "falda gales rojo",
    "falda gales verde", "falda cuatro tablas", "falda vino",
]
REGLAS_FALDA_BASICA = [
    _FaldaBasicaRegla(_FALDAS_ESTANDAR_FRAGS, ["2","4","6","8"], 195),
    _FaldaBasicaRegla(_FALDAS_ESTANDAR_FRAGS, ["10","12","14","16"], 205),
    _FaldaBasicaRegla(_FALDAS_ESTANDAR_FRAGS, ["18","20","28","30","32","34"], 225),
    _FaldaBasicaRegla(_FALDAS_ESTANDAR_FRAGS, ["36","38","40","42"], 235),
    _FaldaBasicaRegla(_FALDAS_ESTANDAR_FRAGS, ["44"], 245),
    _FaldaBasicaRegla(["falda escoces"], ["2","4","6","8"], 215),
    _FaldaBasicaRegla(["falda escoces"], ["10","12","14","16"], 235),
    _FaldaBasicaRegla(["falda escoces"], ["28","30","32","34"], 245),
    _FaldaBasicaRegla(["falda escoces"], ["36","38"], 255),
    _FaldaBasicaRegla(["falda escoces"], ["40","42"], 265),
    _FaldaBasicaRegla(["falda gris"], ["4","6","8","10","12","14","16"], 265),
    _FaldaBasicaRegla(["falda gris"], ["28","30","32","34"], 275),
    _FaldaBasicaRegla(["falda gris"], ["36","38"], 285),
    _FaldaBasicaRegla(["falda gris"], ["40","42"], 295),
]


# ── 7. Pantalón Básico ───────────────────────────────────────────────────────

class _PantalonBasicoRegla(Regla):
    def __init__(self, familia_frags, tallas, precio):
        super().__init__(f"Pantalón Básico {familia_frags} {tallas}", precio)
        self._frags = [f.lower() for f in familia_frags]
        self._tallas = set(tallas)
    def aplica(self, r):
        if r.tipo_pieza != "Pantalón" or r.tipo_prenda != "Básico":
            return False
        nombre = (r.nombre_prod or "").lower()
        return any(f in nombre for f in self._frags) and r.talla in self._tallas

REGLAS_PANTALON_BASICO = [
    # Vestir / Gales
    _PantalonBasicoRegla(["pantalón vestir","pantalon vestir","pantalón gales","pantalon gales"],
        ["2","4","6","8"], 235),
    _PantalonBasicoRegla(["pantalón vestir","pantalon vestir","pantalón gales","pantalon gales"],
        ["10","12","14","16"], 245),
    _PantalonBasicoRegla(["pantalón vestir","pantalon vestir","pantalón gales","pantalon gales"],
        ["18","20","28","30"], 265),
    _PantalonBasicoRegla(["pantalón vestir","pantalon vestir","pantalón gales","pantalon gales"],
        ["32","34"], 285),
    _PantalonBasicoRegla(["pantalón vestir","pantalon vestir","pantalón gales","pantalon gales"],
        ["36","38","40","42"], 295),
    _PantalonBasicoRegla(["pantalón vestir","pantalon vestir","pantalón gales","pantalon gales"],
        ["44"], 315),
    # Escoces
    _PantalonBasicoRegla(["escoces"], ["3","4","6","8"], 199),
    _PantalonBasicoRegla(["escoces"], ["10","12","14","16"], 235),
    _PantalonBasicoRegla(["escoces"], ["28","30","32"], 265),
    # Gabardina
    _PantalonBasicoRegla(["gabardina negro"],
        ["2","4","6","8","10","12","14","16"], 219),
    # Pata de gallo
    _PantalonBasicoRegla(["pata de gallo"], ["4","6","8","10","12","14","16"], 235),
    _PantalonBasicoRegla(["pata de gallo"], ["20","28","30","32"], 245),
    _PantalonBasicoRegla(["pata de gallo"], ["34","36","38","40","42"], 255),
]


# ── 7B. Pantalón Oficial ─────────────────────────────────────────────────────

class _PantalonOficialRegla(Regla):
    def __init__(self, tallas, precio):
        super().__init__(f"Pantalón Oficial Escoces {tallas}", precio)
        self._tallas = set(tallas)
    def aplica(self, r):
        return (
            r.tipo_pieza == "Pantalón"
            and r.tipo_prenda == "Oficial"
            and "escoces" in (r.nombre_prod or "").lower()
            and r.talla in self._tallas
        )

REGLAS_PANTALON_OFICIAL = [
    _PantalonOficialRegla(["2","4","6","8"], 239),
]


# ── 7C. Jumper Básico ────────────────────────────────────────────────────────

class _JumperRegla(Regla):
    def __init__(self, tallas, precio):
        super().__init__(f"Jumper Básico {tallas}", precio)
        self._tallas = set(tallas)
    def aplica(self, r):
        return r.tipo_pieza == "Jumper" and r.tipo_prenda == "Básico" and r.talla in self._tallas

REGLAS_JUMPER = [
    _JumperRegla(["2","4","6","8"], 249),
    _JumperRegla(["10","12","14","16"], 269),
    _JumperRegla(["28","30"], 289),
    _JumperRegla(["32","34"], 309),
    _JumperRegla(["36","38"], 319),
    _JumperRegla(["40","42"], 329),
]


# ── 8. Chamarras ─────────────────────────────────────────────────────────────

class _ChamarraBasicaRegla(Regla):
    def __init__(self, familia_frag, tallas, precio):
        super().__init__(f"Chamarra Básica '{familia_frag}' {tallas}", precio)
        self._frag = familia_frag.lower()
        self._tallas = set(tallas)
    def aplica(self, r):
        return (
            r.tipo_pieza == "Chamarra"
            and r.tipo_prenda == "Básico"
            and self._frag in (r.nombre_prod or "").lower()
            and r.talla in self._tallas
        )

REGLAS_CHAMARRA_BASICA = [
    _ChamarraBasicaRegla("chamarra liso", ["2","4","6","8"], 175),
    _ChamarraBasicaRegla("chamarra liso", ["10","12"], 195),
    _ChamarraBasicaRegla("chamarra liso", ["14","16"], 215),
    _ChamarraBasicaRegla("chamarra liso", ["28","CH","MD","GD","EXG"], 235),
    _ChamarraBasicaRegla("chamarra punto", ["2","4","6","8"], 275),
    _ChamarraBasicaRegla("chamarra punto", ["10","12","14","16"], 295),
    _ChamarraBasicaRegla("chamarra punto", ["28","CH"], 385),
    _ChamarraBasicaRegla("chamarra punto", ["MD"], 395),
    _ChamarraBasicaRegla("chamarra punto", ["GD"], 405),
    _ChamarraBasicaRegla("chamarra punto", ["EXG"], 415),
]

class _ChamarraDeportivaRegla(Regla):
    def __init__(self, nivel, precio):
        super().__init__(f"Chamarra Deportiva {nivel}", precio)
        self._nivel = nivel
    def aplica(self, r):
        return (
            r.tipo_pieza == "Chamarra"
            and r.tipo_prenda == "Deportivo"
            and r.nivel_educativo == self._nivel
            and (r.escudo or "").lower() in ("con escudo", "")
        )

REGLAS_CHAMARRA_DEPORTIVA = [
    _ChamarraDeportivaRegla("Preescolar", 315),
    _ChamarraDeportivaRegla("Primaria",   335),
    _ChamarraDeportivaRegla("Secundaria", 385),
    _ChamarraDeportivaRegla("Bachillerato", 385),
]


# ── 9. Pants 2pz y 3pz ──────────────────────────────────────────────────────

class _PantsRegla(Regla):
    def __init__(self, nivel, tipo, tallas, precio):
        super().__init__(f"{tipo} {nivel} {tallas}", precio)
        self._nivel = nivel
        self._tipo = tipo  # "Pants 2pz" | "Pants 3pz"
        self._tallas = set(tallas)
    def aplica(self, r):
        return (
            r.tipo_pieza == self._tipo
            and r.nivel_educativo == self._nivel
            and r.talla in self._tallas
        )

REGLAS_PANTS = []
for _nivel, _grupos in [
    ("Preescolar", [(["2","4","6","8","10"], 445, 545)]),
    ("Primaria", [
        (["4","6","8","10","12"], 485, 585),
        (["14","16"], 495, 595),
        (["CH","MD","GD"], 585, 685),
    ]),
    ("Secundaria", [
        (["10","12"], 595, 695),
        (["14","16"], 605, 705),
        (["CH","MD","GD","EXG"], 615, 715),
    ]),
    ("Bachillerato", [
        (["16"], 615, 715),
        (["CH","MD","GD","EXG"], 615, 715),
    ]),
]:
    for _tallas, _p2, _p3 in _grupos:
        REGLAS_PANTS.append(_PantsRegla(_nivel, "Pants 2pz", _tallas, _p2))
        REGLAS_PANTS.append(_PantsRegla(_nivel, "Pants 3pz", _tallas, _p3))


# ── 10. Pants Suelto Básico ──────────────────────────────────────────────────

class _PantsSueltoRegla(Regla):
    def __init__(self, atributo_frag, tallas, precio):
        super().__init__(f"Pants Suelto '{atributo_frag}' {tallas}", precio)
        self._frag = atributo_frag.lower()
        self._tallas = set(tallas)
    def aplica(self, r):
        return (
            r.tipo_pieza == "Pants Suelto"
            and r.tipo_prenda == "Básico"
            and self._frag in (r.atributo or "").lower()
            and r.talla in self._tallas
        )

REGLAS_PANTS_SUELTO = [
    _PantsSueltoRegla("liso", ["2","4","6","8"], 165),
    _PantsSueltoRegla("liso", ["10","12","14","16"], 180),
    _PantsSueltoRegla("liso", ["28","CH"], 205),
    _PantsSueltoRegla("liso", ["MD"], 215),
    _PantsSueltoRegla("liso", ["GD"], 225),
    _PantsSueltoRegla("liso", ["EXG"], 235),
    _PantsSueltoRegla("punto", ["2","4","6","8"], 249),
    _PantsSueltoRegla("punto", ["10","12","14","16"], 269),
    _PantsSueltoRegla("punto", ["28","CH"], 309),
    _PantsSueltoRegla("punto", ["MD","GD"], 319),
    _PantsSueltoRegla("punto", ["EXG"], 339),
]


# ── 11. Malla Escolar ────────────────────────────────────────────────────────

class _MallaRegla(Regla):
    def __init__(self, tallas, precio):
        super().__init__(f"Malla Escolar {tallas}", precio)
        self._tallas = set(tallas)
    def aplica(self, r):
        return (
            r.tipo_pieza == "Malla"
            and (r.atributo or "").lower() == "escolar"
            and r.talla in self._tallas
        )

REGLAS_MALLA = [
    _MallaRegla(["0-0","0-2","3-5","6-8"], 109),
    _MallaRegla(["9-12"], 129),
    _MallaRegla(["13-18","CH-MD","GD-EXG","Dama"], 139),
]


# ── 12. Accesorios ───────────────────────────────────────────────────────────

class _AccesorioRegla(Regla):
    def __init__(self, tipo_pieza, atributo_frag, precio):
        super().__init__(f"{tipo_pieza} {atributo_frag}", precio)
        self._pieza = tipo_pieza
        self._atrib = atributo_frag.lower() if atributo_frag else None
    def aplica(self, r):
        if r.tipo_pieza != self._pieza or r.escuela_id is not None:
            return False
        if self._atrib:
            return self._atrib in (r.atributo or "").lower()
        return True

class _PlayeraPoloRegla(Regla):
    def __init__(self, tallas, precio):
        super().__init__(f"Playera Polo Blanca {tallas}", precio)
        self._tallas = set(tallas)
    def aplica(self, r):
        return (
            r.tipo_pieza == "Playera"
            and (r.atributo or "").lower() == "polo"
            and r.escuela_id is None
            and r.talla in self._tallas
        )

REGLAS_ACCESORIOS = [
    _AccesorioRegla("Calceta", "escolar", 49),
    _AccesorioRegla("Guante",  "escolta", 49),
    _AccesorioRegla("Corbata", "", 70),
    _AccesorioRegla("Corbatín","", 70),
    _AccesorioRegla("Moño",    "", 70),
    _AccesorioRegla("Boina",   "escolta", 80),
    _PlayeraPoloRegla(["2","4","6","8"], 135),
    _PlayeraPoloRegla(["10","12"], 145),
    _PlayeraPoloRegla(["14","16","18"], 155),
    _PlayeraPoloRegla(["28","30","32","34","36","38"], 170),
    _PlayeraPoloRegla(["40","42"], 180),
    _PlayeraPoloRegla(["CH","MD"], 185),
    _PlayeraPoloRegla(["GD","EXG"], 195),
]


# ── Todas las reglas ─────────────────────────────────────────────────────────

TODAS_LAS_REGLAS: list[Regla] = (
    REGLAS_PLAYERAS
    + REGLAS_SUETER_BASICO
    + REGLAS_SUETER_OFICIAL
    + REGLAS_CAMISA_BASICA
    + REGLAS_CAMISA_OFICIAL
    + REGLAS_CHALECO_BASICO
    + REGLAS_CHALECO_OFICIAL
    + REGLAS_FALDA_BASICA
    + REGLAS_PANTALON_BASICO
    + REGLAS_PANTALON_OFICIAL
    + REGLAS_JUMPER
    + REGLAS_CHAMARRA_BASICA
    + REGLAS_CHAMARRA_DEPORTIVA
    + REGLAS_PANTS
    + REGLAS_PANTS_SUELTO
    + REGLAS_MALLA
    + REGLAS_ACCESORIOS
)


# ── Consulta Postgres ────────────────────────────────────────────────────────

QUERY = sa.text("""
SELECT
    v.sku,
    v.talla,
    v.precio_venta::numeric   AS precio_venta,
    p.nombre                  AS nombre_prod,
    p.nombre_base             AS nombre_base,
    p.escudo                  AS escudo,
    p.escuela_id              AS escuela_id,
    tp.nombre                 AS tipo_pieza,
    tpr.nombre                AS tipo_prenda,
    ne.nombre                 AS nivel_educativo,
    ap.nombre                 AS atributo
FROM variante v
JOIN producto p         ON p.id = v.producto_id
LEFT JOIN tipo_pieza  tp  ON tp.id  = p.tipo_pieza_id
LEFT JOIN tipo_prenda tpr ON tpr.id = p.tipo_prenda_id
LEFT JOIN nivel_educativo ne ON ne.id = p.nivel_educativo_id
LEFT JOIN atributo_producto ap ON ap.id = p.atributo_id
ORDER BY tp.nombre, tpr.nombre, p.nombre, v.talla
""")


def main():
    engine = sa.create_engine(DB_URL, future=True)
    try:
        with engine.connect() as conn:
            rows = conn.execute(QUERY).fetchall()
    except Exception as e:
        print(f"ERROR conectando a Postgres: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Variantes cargadas: {len(rows)}\n")

    inconsistencias = []

    for row in rows:
        mejor_regla = None
        mejor_objetivo = 0
        aplico_alguna = False

        for regla in TODAS_LAS_REGLAS:
            resultado = regla.chequear(row)
            if resultado is None:
                continue
            aplico_alguna = True
            incumple, objetivo = resultado
            if objetivo > mejor_objetivo:
                mejor_objetivo = objetivo
                mejor_regla = regla
                if incumple:
                    pass  # seguimos buscando la regla de mayor objetivo

        if mejor_regla and row.precio_venta < mejor_objetivo:
            inconsistencias.append({
                "sku": row.sku,
                "nombre": row.nombre_prod,
                "talla": row.talla,
                "precio_actual": float(row.precio_venta),
                "precio_objetivo": mejor_objetivo,
                "diferencia": mejor_objetivo - float(row.precio_venta),
                "regla": mejor_regla.descripcion,
            })

    if not inconsistencias:
        print("✅ Sin inconsistencias — todos los precios cumplen las reglas.")
        return

    # Agrupar por tipo de regla
    from collections import defaultdict
    por_regla: dict[str, list] = defaultdict(list)
    for inc in inconsistencias:
        por_regla[inc["regla"]].append(inc)

    print(f"⚠️  INCONSISTENCIAS ENCONTRADAS: {len(inconsistencias)} variantes\n")
    print(f"{'SKU':<30} {'Nombre':<55} {'Talla':<6} {'Actual':>8} {'Objetivo':>10} {'Diff':>6}")
    print("-" * 125)

    total_diff = 0
    for regla_desc in sorted(por_regla.keys()):
        items = sorted(por_regla[regla_desc], key=lambda x: (x["nombre"], x["talla"]))
        print(f"\n── {regla_desc} ──")
        for inc in items:
            print(
                f"  {inc['sku']:<28} {inc['nombre']:<55} {inc['talla']:<6}"
                f" ${inc['precio_actual']:>7.2f}  ${inc['precio_objetivo']:>8}  +${inc['diferencia']:>5.0f}"
            )
            total_diff += inc["diferencia"]

    print(f"\n{'='*125}")
    print(f"Total variantes con precio bajo: {len(inconsistencias)}")
    print(f"Impacto acumulado si se actualizan: +${total_diff:,.0f} en precios")


def aplicar_correcciones():
    engine = sa.create_engine(DB_URL, future=True)
    with engine.connect() as conn:
        rows = conn.execute(QUERY).fetchall()

    inconsistencias = []
    for row in rows:
        mejor_regla = None
        mejor_objetivo = 0
        for regla in TODAS_LAS_REGLAS:
            resultado = regla.chequear(row)
            if resultado is None:
                continue
            incumple, objetivo = resultado
            if objetivo > mejor_objetivo:
                mejor_objetivo = objetivo
                mejor_regla = regla
        if mejor_regla and row.precio_venta < mejor_objetivo:
            inconsistencias.append({"sku": row.sku, "precio_objetivo": mejor_objetivo,
                                    "precio_actual": float(row.precio_venta),
                                    "nombre": row.nombre_prod, "talla": row.talla})

    if not inconsistencias:
        print("Sin inconsistencias, nada que actualizar.")
        return

    UPDATE_SQL = sa.text(
        "UPDATE variante SET precio_venta = :precio WHERE sku = :sku"
    )
    with engine.begin() as conn:
        for inc in inconsistencias:
            conn.execute(UPDATE_SQL, {"precio": inc["precio_objetivo"], "sku": inc["sku"]})

    print(f"Actualizadas {len(inconsistencias)} variantes:")
    for inc in sorted(inconsistencias, key=lambda x: (x["nombre"], x["talla"])):
        print(f"  {inc['sku']:<28} {inc['nombre']:<55} {inc['talla']:<6}"
              f"  ${inc['precio_actual']:.2f} -> ${inc['precio_objetivo']}")


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == "aplicar":
        aplicar_correcciones()
    else:
        main()
