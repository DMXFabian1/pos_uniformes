#!/usr/bin/env python3
"""Sincroniza cambios de catálogo de Mac (local) a Windows (producción).

Uso — desde la raíz del repo, con el venv activado:
    python pos_uniformes/scripts/sync_catalog_to_windows.py

Cuándo ejecutar:
    Al regresar a la tienda después de haber trabajado en modo local (sin LAN).

Qué sincroniza:
    - catalog_school_product_link  → todos los links (ON CONFLICT DO UPDATE)
    - producto                     → solo registros nuevos que no existen en Windows
    - variante                     → solo registros nuevos (no toca stock/precios de Windows)
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, text

WINDOWS_HOST = "192.168.0.10"
WINDOWS_PORT = 5432


def _build_urls() -> tuple[str, str]:
    """Lee credenciales del .env y construye URLs para local y Windows."""
    from pos_uniformes.utils.config import load_runtime_env_overrides
    import os

    ov = load_runtime_env_overrides()

    def _v(key: str, default: str) -> str:
        return os.getenv(key, ov.get(key, default))

    user = _v("POS_UNIFORMES_DB_USER", "postgres")
    pw = _v("POS_UNIFORMES_DB_PASSWORD", "postgres")
    port = _v("POS_UNIFORMES_DB_PORT", "5432")
    name = _v("POS_UNIFORMES_DB_NAME", "pos_uniformes")

    local = f"postgresql+psycopg://{user}:{pw}@localhost:{port}/{name}"
    windows = f"postgresql+psycopg://{user}:{pw}@{WINDOWS_HOST}:{port}/{name}"
    return local, windows


def _check_windows_reachable() -> bool:
    try:
        s = socket.create_connection((WINDOWS_HOST, WINDOWS_PORT), timeout=2)
        s.close()
        return True
    except OSError:
        return False


def _sync_catalog_links(local_conn, win_conn) -> int:
    rows = local_conn.execute(
        text("SELECT escuela_id, producto_id, activo, created_at FROM catalog_school_product_link")
    ).fetchall()
    for r in rows:
        win_conn.execute(
            text("""
                INSERT INTO catalog_school_product_link (escuela_id, producto_id, activo, created_at)
                VALUES (:eid, :pid, :activo, :ts)
                ON CONFLICT ON CONSTRAINT uq_school_product_link
                DO UPDATE SET activo = EXCLUDED.activo
            """),
            {"eid": r.escuela_id, "pid": r.producto_id, "activo": r.activo, "ts": r.created_at},
        )
    win_conn.commit()
    return len(rows)


def _sync_new_rows(local_conn, win_conn, table: str) -> int:
    win_ids = {r[0] for r in win_conn.execute(text(f"SELECT id FROM {table}")).fetchall()}
    local_ids = {r[0] for r in local_conn.execute(text(f"SELECT id FROM {table}")).fetchall()}
    new_ids = local_ids - win_ids
    if not new_ids:
        return 0

    rows = local_conn.execute(
        text(f"SELECT * FROM {table} WHERE id = ANY(:ids)"),
        {"ids": list(new_ids)},
    ).fetchall()
    cols = list(local_conn.execute(text(f"SELECT * FROM {table} LIMIT 0")).keys())
    col_str = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)

    for row in rows:
        win_conn.execute(
            text(f"INSERT INTO {table} ({col_str}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"),
            dict(zip(cols, row)),
        )
    win_conn.commit()
    return len(rows)


def main() -> int:
    if not _check_windows_reachable():
        print("❌  Windows DB no disponible (192.168.0.10:5432).")
        print("    Conéctate a la red de la tienda y vuelve a intentarlo.")
        return 1

    print(f"✅  Windows DB disponible. Iniciando sincronización...\n")

    local_url, windows_url = _build_urls()
    local_eng = create_engine(local_url, connect_args={"connect_timeout": 5})
    win_eng = create_engine(windows_url, connect_args={"connect_timeout": 5})

    with local_eng.connect() as lc, win_eng.connect() as wc:
        n = _sync_catalog_links(lc, wc)
        print(f"🔗  catalog_school_product_link : {n} registros sincronizados")

        n = _sync_new_rows(lc, wc, "producto")
        print(f"📦  productos nuevos            : {n}")

        n = _sync_new_rows(lc, wc, "variante")
        print(f"📐  variantes nuevas            : {n}")

    print("\n✅  Listo. Regenera el panel en Windows:")
    print("    python scripts\\generar_panel_uniformes.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
