"""Recalcula las comisiones ya anotadas en la Libreta con la regla vigente.

Cuando cambia la regla (2026-09-06: el conjunto 3pz pasó de 3 a 2
comisiones) los registros viejos siguen con el número de antes. Este script
vuelve a calcular `comisiones` desde el `detalle` de cada venta/apartado y
solo toca los que cambian. Los abonos no se tocan (siempre 0).

Uso (desde la raíz del repo, con el venv):
    python -m pos_uniformes.scripts.recalcular_comisiones_libreta            # solo muestra
    python -m pos_uniformes.scripts.recalcular_comisiones_libreta --aplicar  # guarda
    python -m pos_uniformes.scripts.recalcular_comisiones_libreta --desde 2026-09-01
"""

from __future__ import annotations

import argparse
from datetime import date, datetime

from sqlalchemy import select

from pos_uniformes.database.connection import SessionLocal
from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services.libreta_service import comisiones_de_items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--aplicar", action="store_true", help="guarda los cambios")
    parser.add_argument(
        "--desde", type=date.fromisoformat, default=None,
        help="solo registros desde esta fecha (AAAA-MM-DD); por defecto todos",
    )
    args = parser.parse_args()

    cambios: list[tuple[int, str, str, int, int]] = []
    with SessionLocal() as session:
        stmt = select(LibretaVenta).where(LibretaVenta.tipo != "abono")
        if args.desde:
            stmt = stmt.where(
                LibretaVenta.created_at >= datetime.combine(args.desde, datetime.min.time())
            )
        for row in session.scalars(stmt.order_by(LibretaVenta.created_at)):
            nuevo = comisiones_de_items(list(row.detalle or []))
            actual = int(row.comisiones or 0)
            if nuevo != actual:
                cambios.append(
                    (row.id, row.created_at.strftime("%d/%m/%Y %H:%M"),
                     row.employee_code, actual, nuevo)
                )
                if args.aplicar:
                    row.comisiones = nuevo
        if args.aplicar and cambios:
            session.commit()

    if not cambios:
        print("Nada que cambiar: todas las comisiones ya van con la regla vigente.")
        return 0
    print(f"{len(cambios)} registro(s) {'actualizados' if args.aplicar else 'cambiarían'}:")
    for rid, fecha, code, antes, despues in cambios:
        print(f"  #{rid:<6} {fecha}  {code:<8} {antes} -> {despues}")
    if not args.aplicar:
        print("\nSolo vista previa. Corre con --aplicar para guardar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
