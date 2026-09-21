"""Arma el uniforme de cada escuela con lo que la base ya sabe (catálogo,
fase 2): sus productos activos más los generales ligados, en el orden del
tarifario, agrupados en Diario / Deportivo / Escolta / Accesorio por el tipo
de prenda. No toca productos ni SKUs; solo crea `uniforme` y `uniforme_pieza`.
Idempotente: si la escuela ya tiene uniforme, solo agrega las piezas que faltan.

Lo que la base NO sabe (qué pants/short/playera general usa cada escuela,
colores, opcionales) lo completa Daniel en el POS: Más → Uniformes por escuela.

Uso:
  python -m pos_uniformes.scripts.armar_uniformes                # dry-run, todas
  python -m pos_uniformes.scripts.armar_uniformes --escuela 53   # una escuela
  python -m pos_uniformes.scripts.armar_uniformes --aplicar
"""

from __future__ import annotations

import argparse
import sys

from pos_uniformes.database.connection import get_session
from pos_uniformes.services import uniforme_service as us


def imprimir(filas: list[dict], *, salida=sys.stdout) -> None:
    for f in filas:
        estado = "ya armado" if f["armado"] else "propuesta"
        print(f"\n== {f['escuela']} (#{f['escuela_id']}) — {estado}: {f['propias']} propias, {f['generales']} generales", file=salida)
        if not f["piezas"]:
            print("   (sin piezas: la escuela no tiene productos activos ni ligas)", file=salida)
        for p in f["piezas"]:
            marca = "·" if p["origen"] == "Escuela" else "○"
            color = f"  color: {p['color']}" if p["color"] else ""
            print(f"   {marca} {p['grupo']:<10} {p['tipo_pieza']:<13} {p['nombre']}{color}", file=salida)
    armadas = sum(1 for f in filas if f["armado"])
    print(f"\n{len(filas)} escuelas; {armadas} ya con uniforme, {len(filas) - armadas} por armar.", file=salida)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--escuela", type=int, help="solo esta escuela (id)")
    ap.add_argument("--aplicar", action="store_true", help="escribe; sin esto solo muestra")
    args = ap.parse_args(argv)

    with get_session() as session:
        filas = us.resumen(session)
        if args.escuela is not None:
            filas = [f for f in filas if f["escuela_id"] == args.escuela]
            if not filas:
                print("No existe esa escuela (o está inactiva).")
                return 1
        imprimir(filas)
        if not args.aplicar:
            print("\nDry-run. Agrega --aplicar para escribir.")
            return 0
        for f in filas:
            us.armar(session, f["escuela_id"])
        session.commit()
        print("Aplicado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
