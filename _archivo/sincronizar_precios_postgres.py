"""
Sincroniza precios desde productos.db (SQLite) hacia PostgreSQL.
Usa CatalogService.aplicar_cambio_masivo_precio para dejar registro
en cambio_catalogo (historial del POS).

Uso:
    python sincronizar_precios_postgres.py
    python sincronizar_precios_postgres.py --dry-run
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import RolUsuario, Usuario, Variante
from pos_uniformes.services.catalog_service import CatalogService
from sqlalchemy import select


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def resolve_sqlite_path() -> Path:
    root = Path(__file__).resolve().parent
    candidates = [
        root / "Gestor_de_Inventarios" / "data" / "productos.db",
        Path.cwd() / "productos.db",
        root / "data" / "productos.db",
        Path.home() / "Downloads" / "Gestor_de_Inventarios" / "data" / "productos.db",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"No se encontró productos.db. Candidatos: {candidates}")


def main(dry_run: bool = False) -> None:
    # 1. Leer precios objetivo desde SQLite
    sqlite_path = resolve_sqlite_path()
    log(f"SQLite: {sqlite_path}")

    conn = sqlite3.connect(str(sqlite_path))
    rows = conn.execute("SELECT sku, precio FROM productos").fetchall()
    conn.close()
    precios_sqlite: dict[str, Decimal] = {
        sku: Decimal(str(precio)) for sku, precio in rows if precio is not None
    }
    log(f"Precios leídos de SQLite: {len(precios_sqlite)}")

    with get_session() as session:
        # 2. Obtener usuario admin
        admin = session.scalar(
            select(Usuario).where(Usuario.rol == RolUsuario.ADMIN, Usuario.activo == True).limit(1)
        )
        if admin is None:
            log("ERROR: No se encontró usuario ADMIN activo en PostgreSQL")
            sys.exit(1)
        log(f"Usuario: {admin.username} (id={admin.id})")

        # 3. Mapear SKU → Variante
        variantes = session.scalars(select(Variante)).all()
        variante_por_sku: dict[str, Variante] = {v.sku: v for v in variantes}
        log(f"Variantes en Postgres: {len(variante_por_sku)}")

        # 4. Calcular cambios (solo subidas)
        precios_por_variante: list[tuple[int, Decimal]] = []
        sin_match = []
        sin_cambio = 0
        bajaria = 0

        for sku, precio_nuevo in precios_sqlite.items():
            variante = variante_por_sku.get(sku)
            if variante is None:
                sin_match.append(sku)
                continue
            precio_actual = Decimal(str(variante.precio_venta))
            if precio_nuevo > precio_actual:
                precios_por_variante.append((variante.id, precio_nuevo))
            elif precio_nuevo == precio_actual:
                sin_cambio += 1
            else:
                bajaria += 1

        log(f"  Suben   : {len(precios_por_variante)}")
        log(f"  Sin cambio: {sin_cambio}")
        log(f"  Bajarían (omitidos): {bajaria}")
        log(f"  Sin match en Postgres: {len(sin_match)}")

        if sin_match:
            log(f"  SKUs sin match (primeros 10): {sin_match[:10]}")

        if not precios_por_variante:
            log("No hay precios que actualizar — todo está al día.")
            return

        if dry_run:
            log("DRY RUN — no se aplican cambios.")
            for vid, precio in precios_por_variante[:10]:
                v = next(x for x in variantes if x.id == vid)
                log(f"  {v.sku}: ${v.precio_venta} → ${precio}")
            if len(precios_por_variante) > 10:
                log(f"  ... y {len(precios_por_variante) - 10} más")
            return

        # 5. Aplicar con historial
        fecha = datetime.now().strftime("%Y-%m-%d")
        resumen = CatalogService.aplicar_cambio_masivo_precio(
            session=session,
            usuario=admin,
            referencia=f"SYNC-{fecha}",
            motivo="Sincronización desde Gestor de Precios",
            observacion="Sesión 2026-04-23 — revisión completa de escaleras",
            precios_por_variante=precios_por_variante,
        )
        session.commit()

        log("=" * 50)
        log("SINCRONIZACIÓN COMPLETADA")
        log(f"  Aplicadas : {resumen['aplicadas']}")
        log(f"  Sin cambio: {resumen['sin_cambios']}")
        log(f"  Subieron  : {resumen['suben']}")
        log(f"  Bajaron   : {resumen['bajan']}")
        log("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Muestra cambios sin aplicar")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
