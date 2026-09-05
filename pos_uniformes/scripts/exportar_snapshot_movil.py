"""Exporta el snapshot SQLite para el servidor PWA de la casa.

La PC de la tienda se apaga en las noches, así que la PWA no puede leer
la base en vivo: este script copia las tablas que la app móvil necesita
a un archivo SQLite que se manda a la PC de la casa (siempre prendida).
El servidor de allá lo lee con POS_UNIFORMES_DB_URL=sqlite:///...

Uso (en la PC principal):
    python -m pos_uniformes.scripts.exportar_snapshot_movil [salida.sqlite]
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Tablas que la Fase 1 (solo lectura) necesita. Empleada incluye pin_hash:
# el login de la PWA se valida contra el snapshot.
_TABLAS = (
    "empleada",
    "empleada_horario",
    "empleada_evento",
    "libreta_corte",
    "libreta_venta",
)
# libreta_venta se recorta a los últimos N días (los ciclos y "hoy" no
# necesitan más, y el archivo se mantiene chico).
_DIAS_VENTAS = 120


def exportar(destino: Path) -> dict[str, int]:
    from sqlalchemy import create_engine, select

    from pos_uniformes.database import models
    from pos_uniformes.database.connection import engine as engine_origen

    tmp = destino.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    sqlite_engine = create_engine(f"sqlite:///{tmp}")

    tablas_orm = {
        "empleada": models.Empleada,
        "empleada_horario": models.EmpleadaHorario,
        "empleada_evento": models.EmpleadaEvento,
        "libreta_corte": models.LibretaCorte,
        "libreta_venta": models.LibretaVenta,
    }
    conteos: dict[str, int] = {}
    corte_ventas = datetime.now().astimezone() - timedelta(days=_DIAS_VENTAS)

    with engine_origen.connect() as origen, sqlite_engine.begin() as sqlite_conn:
        for nombre in _TABLAS:
            modelo = tablas_orm[nombre]
            modelo.__table__.create(sqlite_conn)
            stmt = select(modelo.__table__)
            if nombre == "libreta_venta":
                stmt = stmt.where(modelo.created_at >= corte_ventas)
            filas = [dict(r._mapping) for r in origen.execute(stmt)]
            if filas:
                sqlite_conn.execute(modelo.__table__.insert(), filas)
            conteos[nombre] = len(filas)

    sqlite_engine.dispose()
    tmp.replace(destino)  # swap atómico: el servidor nunca ve un archivo a medias
    return conteos


def main() -> int:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("snapshot_movil.sqlite")
    conteos = exportar(destino)
    total = sum(conteos.values())
    print(f"Snapshot listo: {destino} ({total} filas)")
    for nombre, n in conteos.items():
        print(f"  {nombre}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
