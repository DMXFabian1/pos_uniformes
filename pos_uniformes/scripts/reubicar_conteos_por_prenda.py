"""Pone cada talla capturada en la jornada de SU prenda.

Hasta el 20/09 la captura de una jornada de una sola prenda de básicos
mostraba todas las prendas del tipo (bug), así que lo capturado de "Camisa
Cuello olan Azul/Blanca/Rojo" quedó dentro de la jornada de "…Vino", y las
jornadas de esas prendas quedaron "a medias" con 0. Este script mueve cada
renglón a la jornada de su prenda (la que ya existe de esa misma persona, o
una nueva a su nombre), y deja la jornada destino en el mismo estado que la
de origen (terminada / aplicada). Los renglones no cambian: lo contado y lo
aplicado al inventario siguen igual; solo cambia en qué jornada están.

Uso:  python -m pos_uniformes.scripts.reubicar_conteos_por_prenda [--aplicar]
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict

from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import ConteoInventario, ConteoJornada, Producto, Variante
from pos_uniformes.services import conteo_jornada_service as jn


def _corto(nombre: str) -> str:
    return str(nombre or "").split("|")[0].strip()


def planear(session) -> list[dict]:
    """[{origen, prenda, renglones, destino (jornada o None)}] de lo que hay que mover."""
    plan = []
    jornadas = list(session.scalars(select(ConteoJornada).where(ConteoJornada.escuela_id.is_(None), ConteoJornada.prenda != "").order_by(ConteoJornada.id)).all())
    for j in jornadas:
        filas = session.execute(
            select(ConteoInventario, Producto.nombre)
            .join(Variante, Variante.id == ConteoInventario.variante_id)
            .join(Producto, Producto.id == Variante.producto_id)
            .where(ConteoInventario.jornada_id == j.id)
        ).all()
        ajenas: dict[str, list[ConteoInventario]] = defaultdict(list)
        for c, producto in filas:
            if str(producto) != j.prenda:
                ajenas[str(producto)].append(c)
        for prenda, renglones in ajenas.items():
            destino = next((
                d for d in jornadas
                if d.prenda == prenda and d.tipo_pieza == j.tipo_pieza and d.empleada_code == j.empleada_code and d.id != j.id
            ), None)
            plan.append({"origen": j, "prenda": prenda, "renglones": renglones, "destino": destino})
    return plan


def aplicar(session, plan: list[dict]) -> int:
    movidos = 0
    for paso in plan:
        origen, destino = paso["origen"], paso["destino"]
        if destino is None:
            destino = ConteoJornada(
                escuela_id=None, tipo_pieza=origen.tipo_pieza, prenda=paso["prenda"],
                titulo=f"Básicos · {jn.nombre_corto_prenda(paso['prenda'])}"[:160],
                empleada_code=origen.empleada_code, empleada_nombre=origen.empleada_nombre,
                total_tallas=len(paso["renglones"]), iniciada_at=origen.iniciada_at,
            )
            session.add(destino)
            session.flush()
            paso["destino"] = destino
        for c in paso["renglones"]:
            c.jornada_id = destino.id
            session.add(c)
            movidos += 1
        # La destino queda como la origen: terminada y/o aplicada.
        if origen.terminada_at is not None and destino.terminada_at is None:
            destino.terminada_at = origen.terminada_at
        if origen.revisada_at is not None and destino.revisada_at is None:
            destino.revisada_at, destino.revisada_por = origen.revisada_at, origen.revisada_por
        if not destino.total_tallas:
            destino.total_tallas = len(paso["renglones"])
        session.add(destino)
    session.flush()
    return movidos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="sin esto solo enseña")
    args = parser.parse_args(argv)
    with get_session() as session:
        plan = planear(session)
        if not plan:
            print("Nada que mover: cada talla está en la jornada de su prenda.")
            return 0
        for p in plan:
            o, d = p["origen"], p["destino"]
            a_donde = f"#{d.id} ({'a medias' if d.terminada_at is None else 'terminada'})" if d else "una jornada NUEVA"
            print(f"#{o.id} {o.titulo[:40]:40} → {len(p['renglones']):3} tallas de {_corto(p['prenda']):32} a {a_donde}")
        print(f"\n{sum(len(p['renglones']) for p in plan)} renglones en {len(plan)} movimientos.")
        if not args.aplicar:
            print("Solo fue un vistazo. Con --aplicar se mueven de verdad.")
            return 0
        n = aplicar(session, plan)
        session.commit()
        print(f"Listo: {n} renglones reubicados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
