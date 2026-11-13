"""Orden natural de tallas (puro): el de filtros, Bodega y la tabla de Inventario.

1. Números y rangos de edad ascendentes («0-2», «4», «9-12», «10»…).
2. Letras mexicanas: XCH, CH, CH-MD, MD, GD, GD-EXG, EXG, 2XG.
3. Letras en inglés (las usan conteo, pedidos y tarifarios): XXS, XS, S, M,
   L, XL, XXL, 2XL/XXXL.
4. Especiales: UNI, UNITALLA, DAMA, ESP.
5. Cualquier otra, alfabética al final.
"""

from __future__ import annotations

import re

_RANGO_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
_NUMERO_RE = re.compile(r"^\s*(\d+)\s*$")

ORDEN_LETRAS = {
    "XCH": 5,
    "CH": 10,
    "CH-MD": 15,
    "MD": 20,
    "GD": 30,
    "GD-EXG": 35,
    "EXG": 40,
    "2XG": 45,
    "XXG": 45,
    "XXS": 51,
    "XS": 52,
    "S": 53,
    "M": 54,
    "L": 55,
    "XL": 56,
    "XXL": 57,
    "2XL": 58,
    "XXXL": 59,
    "UNI": 80,
    "UNITALLA": 81,
    "DAMA": 90,
    "ESP": 91,
}

TALLAS_ESPECIALES = frozenset({"UNI", "UNITALLA", "DAMA", "ESP"})


def clave_talla(talla: object) -> tuple[object, ...]:
    """Clave de `sorted` para una talla."""
    normal = str(talla or "").strip().upper()

    rango = _RANGO_RE.match(normal)
    if rango:
        inicio, fin = int(rango.group(1)), int(rango.group(2))
        return (0, inicio, 1, fin, normal)

    numero = _NUMERO_RE.match(normal)
    if numero:
        n = int(numero.group(1))
        return (0, n, 0, n, normal)

    if normal in ORDEN_LETRAS:
        return (1, ORDEN_LETRAS[normal], normal)

    return (2, normal)


def es_talla_numerica(talla: object) -> bool:
    normal = str(talla or "").strip().upper()
    return bool(_NUMERO_RE.match(normal) or _RANGO_RE.match(normal))
