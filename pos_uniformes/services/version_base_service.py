"""¿El código que corre va en la misma versión de base que la tienda?

En la copia de casa (POS_PWA_MODO=casa) la base la trae la tienda: si la tienda
se actualizó y casa no (o al revés), alguna consulta puede pedir una columna que
no existe. Se compara la revisión de alembic de la base con las migraciones que
conoce este código, sin alembic (solo se leen los archivos de versions/):

- "igual": la base va en la cabeza de este código.
- "casa_mas_vieja": la base trae una revisión que este código no conoce.
- "casa_mas_nueva": este código tiene migraciones que la base aún no tiene.
- "desconocida": no se pudo leer (sin tabla alembic_version, sin conexión…).

Lo usa /health en modo casa; el latido de nucleo avisa si no es "igual".
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text

VERSIONES = Path(__file__).resolve().parents[1] / "migrations" / "versions"
_REV = re.compile(r"""^revision\s*(?::[^=]*)?=\s*["']([^"']+)["']""", re.M)
_ABAJO = re.compile(r"""^down_revision\s*(?::[^=]*)?=\s*(.+)$""", re.M)


@lru_cache(maxsize=1)
def revisiones_del_codigo(carpeta: Path = VERSIONES) -> tuple[frozenset[str], frozenset[str]]:
    """(todas las revisiones, las cabezas: las que ninguna otra tiene de anterior)."""
    todas: set[str] = set()
    anteriores: set[str] = set()
    for archivo in carpeta.glob("*.py"):
        texto = archivo.read_text(encoding="utf-8")
        rev = _REV.search(texto)
        if not rev:
            continue
        todas.add(rev.group(1))
        abajo = _ABAJO.search(texto)
        if abajo:
            anteriores.update(re.findall(r"""["']([^"']+)["']""", abajo.group(1)))
    return frozenset(todas), frozenset(todas - anteriores)


def comparar(base: set[str], todas: frozenset[str], cabezas: frozenset[str]) -> str:
    if not base or not cabezas:
        return "desconocida"
    if base == set(cabezas):
        return "igual"
    if base - todas:
        return "casa_mas_vieja"
    return "casa_mas_nueva"


def estado_version(db) -> str:
    """Compara la base de la sesión con este código (ver arriba). Nunca truena."""
    try:
        if db.get_bind().dialect.name != "postgresql":
            return "desconocida"
        base = {fila[0] for fila in db.execute(text("SELECT version_num FROM alembic_version"))}
    except Exception:  # noqa: BLE001 — es un extra de /health
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return "desconocida"
    todas, cabezas = revisiones_del_codigo()
    return comparar(base, todas, cabezas)
