"""Normalización, clasificación y enmascarado del teléfono del cliente (E1-A).

Regla (K6), sobre los dígitos del teléfono:

- sin dígitos → vacío (``None``);
- 10 dígitos → esos 10;
- 12 dígitos que empiezan con ``52`` → los últimos 10;
- 13 dígitos que empiezan con ``521`` → los últimos 10;
- cualquier otra longitud, o un resultado con todos los dígitos iguales
  (``0000000000``) → inválido (``None``).

El teléfono original nunca se modifica: esto solo produce el valor derivado
``cliente.telefono_normalizado``. La migración ``e1a_identidad_cliente`` usa la
versión SQL de esta misma regla (``SQL_NORMALIZAR_TELEFONO``); una prueba
verifica que las dos coinciden.
"""

from __future__ import annotations

import re

VACIO = "vacio"
VALIDO = "valido"
INVALIDO = "invalido"

_NO_DIGITOS = re.compile(r"\D")
_REPETIDO = re.compile(r"^(\d)\1+$")

# Expresión SQL (PostgreSQL) equivalente a `normalizar_telefono`, sobre la
# columna `telefono`. La usa la migración para rellenar la columna nueva.
SQL_NORMALIZAR_TELEFONO = """
(SELECT CASE WHEN c ~ '^(\\d)\\1+$' THEN NULL ELSE c END
   FROM (SELECT CASE
                  WHEN length(d) = 10 THEN d
                  WHEN length(d) = 12 AND d LIKE '52%' THEN right(d, 10)
                  WHEN length(d) = 13 AND d LIKE '521%' THEN right(d, 10)
                  ELSE NULL
                END AS c
           FROM (SELECT regexp_replace(coalesce(telefono, ''), '\\D', '', 'g') AS d) AS solo_digitos
        ) AS candidato)
""".strip()


def solo_digitos(telefono: str | None) -> str:
    return _NO_DIGITOS.sub("", telefono or "")


def normalizar_telefono(telefono: str | None) -> str | None:
    """Devuelve los 10 dígitos del teléfono, o ``None`` si está vacío o es inválido."""
    d = solo_digitos(telefono)
    if len(d) == 10:
        candidato = d
    elif len(d) == 12 and d.startswith("52"):
        candidato = d[-10:]
    elif len(d) == 13 and d.startswith("521"):
        candidato = d[-10:]
    else:
        return None
    if _REPETIDO.match(candidato):
        return None
    return candidato


def clasificar_telefono(telefono: str | None) -> str:
    """``vacio`` si no trae dígitos; ``valido`` si se normaliza; si no, ``invalido``."""
    if not solo_digitos(telefono):
        return VACIO
    return VALIDO if normalizar_telefono(telefono) is not None else INVALIDO


def enmascarar_telefono(telefono: str | None) -> str:
    """Muestra solo los últimos 4 dígitos: ``•••• ••12 34``. Vacío si no hay dígitos."""
    d = normalizar_telefono(telefono) or solo_digitos(telefono)
    if not d:
        return ""
    ultimos = d[-4:]
    return f"•••• ••{ultimos[:2]} {ultimos[2:]}" if len(ultimos) == 4 else "•••• ••••"
