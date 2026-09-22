"""Catálogo, fase 3: la receta de cada conjunto (Pants 3pz = Pants 2pz +
Playera; Chamarra = sale de un Pants 2pz y deja un Pants Suelto) y el stock
calculado de sus piezas.

Busca las piezas entre las del uniforme de la escuela (si está armado) o
entre sus productos activos, y solo propone cuando hay UNA prenda de cada
tipo; lo ambiguo o lo que falta se lista para que Daniel lo resuelva en el
POS (Más → Uniformes por escuela → Receta…). No toca SKUs ni precios.
Con --aplicar guarda las recetas propuestas y sincroniza el stock de TODOS
los conjuntos con receta (movimientos `derivado:`).

Uso:
  python -m pos_uniformes.scripts.armar_recetas            # dry-run
  python -m pos_uniformes.scripts.armar_recetas --aplicar
"""

from __future__ import annotations

import argparse
import sys

from pos_uniformes.database.connection import get_session
from pos_uniformes.services import conjunto_service as cs


def imprimir(filas: list[dict], *, salida=sys.stdout) -> tuple[int, int, int]:
    con, propuestas, pendientes = 0, 0, 0
    for f in filas:
        cab = f"{f['escuela']} · {f['nombre']}"
        if f["receta"]:
            con += 1
            extra = f"   ⚠ tallas sin pieza: {', '.join(f['tallas_sin_pieza'])}" if f["tallas_sin_pieza"] else ""
            print(f"✓ {cab}: {f['receta']}{extra}", file=salida)
            continue
        prop = f["propuesta"] or {}
        if prop.get("componentes"):
            propuestas += 1
            print(f"→ {cab}: {prop['texto']}", file=salida)
        else:
            pendientes += 1
            motivos = []
            if prop.get("faltan"):
                motivos.append("falta " + ", ".join(prop["faltan"]))
            for tipo, nombres in (prop.get("ambiguas") or {}).items():
                motivos.append(f"{tipo}: hay {len(nombres)} ({' / '.join(nombres)})")
            print(f"? {cab}: {'; '.join(motivos) or 'sin escuela'}", file=salida)
    print(f"\n{len(filas)} conjuntos: {con} con receta, {propuestas} por armar, {pendientes} para Daniel.", file=salida)
    return con, propuestas, pendientes


def _con_texto(session, filas: list[dict]) -> list[dict]:
    from pos_uniformes.database.models import Producto

    for f in filas:
        prop = f.get("propuesta")
        if prop and prop.get("componentes"):
            # Las piezas del mismo grupo son alternativas: van con "o"
            grupos: dict[tuple[int, bool], list[str]] = {}
            for pid, cant, grupo in prop["componentes"]:
                p = session.get(Producto, pid)
                grupos.setdefault((grupo, cant > 0), []).append(p.nombre if p else str(pid))
            partes = [
                ("+ " if positivo else "deja ") + " o ".join(nombres)
                for (_g, positivo), nombres in grupos.items()
            ]
            prop["texto"] = " ".join(partes).lstrip("+ ")
    return filas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aplicar", action="store_true", help="guarda las recetas propuestas y sincroniza el stock")
    args = ap.parse_args(argv)
    with get_session() as session:
        filas = _con_texto(session, cs.resumen(session))
        imprimir(filas)
        if not args.aplicar:
            print("\nDry-run. Agrega --aplicar para escribir.")
            return 0
        from sqlalchemy import func, select

        from pos_uniformes.database.models import MovimientoInventario

        def derivados() -> int:
            return int(session.scalar(select(func.count()).where(MovimientoInventario.referencia.like(f"{cs.PREFIJO_DERIVADO}%"))) or 0)

        antes = derivados()
        guardadas = 0
        for f in filas:
            prop = f.get("propuesta")
            if prop and prop.get("componentes"):
                cs.definir_receta(session, f["conjunto_id"], prop["componentes"], creado_por="armar_recetas")
                guardadas += 1
        cs.sincronizar_todo(session, creado_por="armar_recetas")
        session.commit()
        print(f"Aplicado: {guardadas} recetas guardadas; {derivados() - antes} tallas de conjuntos con stock recalculado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
