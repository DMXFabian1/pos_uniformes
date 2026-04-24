"""Compara catalogo SQLite vs PostgreSQL y reporta inconsistencias."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class CatalogInconsistencia:
    tipo: str  # "solo_sqlite" | "solo_postgres" | "precio_distinto"
    sku: str
    nombre: str
    precio_sqlite: Decimal | None
    precio_postgres: Decimal | None


def verificar_consistencia(
    session: Session,
    sqlite_path: Path | str,
) -> list[CatalogInconsistencia]:
    """Compara presencia y precios de SKUs entre SQLite (catálogo Windows) y PostgreSQL."""
    conn = sqlite3.connect(str(sqlite_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT sku, nombre, precio FROM productos")
        sqlite_rows: dict[str, tuple[str, Decimal]] = {
            r[0]: (r[1], Decimal(str(r[2]))) for r in cur.fetchall()
        }
    finally:
        conn.close()

    pg_raw = session.execute(
        text("""
        SELECT v.sku, p.nombre, v.precio_venta
        FROM variante v
        JOIN producto p ON p.id = v.producto_id
        WHERE v.activo = true
        """)
    ).fetchall()
    pg_rows: dict[str, tuple[str, Decimal]] = {
        r[0]: (r[1], Decimal(str(r[2]))) for r in pg_raw
    }

    resultado: list[CatalogInconsistencia] = []

    for sku in sorted(sqlite_rows):
        nombre, precio_sq = sqlite_rows[sku]
        if sku not in pg_rows:
            resultado.append(CatalogInconsistencia(
                tipo="solo_sqlite",
                sku=sku,
                nombre=nombre,
                precio_sqlite=precio_sq,
                precio_postgres=None,
            ))
        else:
            precio_pg = pg_rows[sku][1]
            if abs(precio_sq - precio_pg) > Decimal("0.01"):
                resultado.append(CatalogInconsistencia(
                    tipo="precio_distinto",
                    sku=sku,
                    nombre=nombre,
                    precio_sqlite=precio_sq,
                    precio_postgres=precio_pg,
                ))

    for sku in sorted(pg_rows):
        if sku not in sqlite_rows:
            nombre, precio_pg = pg_rows[sku]
            resultado.append(CatalogInconsistencia(
                tipo="solo_postgres",
                sku=sku,
                nombre=nombre,
                precio_sqlite=None,
                precio_postgres=precio_pg,
            ))

    return sorted(resultado, key=lambda x: (x.tipo, x.sku))
