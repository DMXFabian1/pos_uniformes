"""Separa una escuela en dos cuando en realidad son dos planteles distintos que
comparten nombre (Daniel, 2026-09-20: "Álvaro Obregón y Vicente Guerrero son
escuelas que tienen dos niveles distintos y están en lugares distintos").

Se lleva a la escuela NUEVA todos los productos de un nivel educativo (con
sus tallas y SKUs tal cual: nada se reimprime), copia las ligas de catálogo y
la configuración de conteo, y si una jornada de conteo traía tallas de los
dos planteles, la parte en dos (como se hizo con Práxedis el 14/09).

Uso:
  python -m pos_uniformes.scripts.separar_escuela_por_nivel --escuela 43 --nivel Primaria \\
      --nombre "Álvaro Obregón (El Carretón)" [--renombrar-vieja "Álvaro Obregón Preescolar"] [--aplicar]
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    CatalogSchoolProductLink,
    ConfigConteoEscuela,
    ConteoInventario,
    ConteoJornada,
    Escuela,
    NivelEducativo,
    Producto,
    Variante,
)


def planear(session, *, escuela_id: int, nivel: str, nombre_nueva: str) -> dict:
    vieja = session.get(Escuela, escuela_id)
    if vieja is None:
        raise SystemExit(f"No existe la escuela {escuela_id}.")
    niv = session.scalar(select(NivelEducativo).where(NivelEducativo.nombre.ilike(nivel)))
    if niv is None:
        raise SystemExit(f"No existe el nivel {nivel!r}.")
    if session.scalar(select(Escuela).where(Escuela.nombre == nombre_nueva)) is not None:
        raise SystemExit(f"Ya existe una escuela llamada {nombre_nueva!r}.")
    productos = list(session.scalars(
        select(Producto).where(Producto.escuela_id == escuela_id, Producto.nivel_educativo_id == niv.id).order_by(Producto.id)
    ).all())
    se_quedan = list(session.scalars(
        select(Producto).where(Producto.escuela_id == escuela_id, Producto.nivel_educativo_id != niv.id).order_by(Producto.id)
    ).all())
    ids_mueven = {p.id for p in productos}
    jornadas = []
    for j in session.scalars(select(ConteoJornada).where(ConteoJornada.escuela_id == escuela_id)).all():
        filas = session.execute(
            select(ConteoInventario, Variante.producto_id).join(Variante, Variante.id == ConteoInventario.variante_id)
            .where(ConteoInventario.jornada_id == j.id)
        ).all()
        mueven = [c for c, pid in filas if pid in ids_mueven]
        quedan = [c for c, pid in filas if pid not in ids_mueven]
        jornadas.append({"jornada": j, "mueven": mueven, "quedan": quedan})
    return {"vieja": vieja, "nivel": niv, "productos": productos, "se_quedan": se_quedan, "jornadas": jornadas}


def aplicar(session, plan: dict, *, nombre_nueva: str, renombrar_vieja: str | None = None) -> Escuela:
    vieja: Escuela = plan["vieja"]
    nueva = Escuela(nombre=nombre_nueva, activo=True)
    session.add(nueva)
    session.flush()
    for p in plan["productos"]:
        p.escuela_id = nueva.id
        session.add(p)
    for link in session.scalars(select(CatalogSchoolProductLink).where(CatalogSchoolProductLink.escuela_id == vieja.id)).all():
        session.add(CatalogSchoolProductLink(escuela_id=nueva.id, producto_id=link.producto_id, activo=link.activo))
    cfg = session.scalar(select(ConfigConteoEscuela).where(ConfigConteoEscuela.escuela_id == vieja.id))
    if cfg is not None:
        session.add(ConfigConteoEscuela(escuela_id=nueva.id, dias_vigencia=cfg.dias_vigencia))
    for paso in plan["jornadas"]:
        j: ConteoJornada = paso["jornada"]
        if not paso["mueven"]:
            continue
        if not paso["quedan"]:
            j.escuela_id = nueva.id                      # era toda del plantel nuevo
            j.titulo = nombre_nueva[:160]
            session.add(j)
            continue
        j2 = ConteoJornada(                            # había de los dos: se parte, mismos datos
            escuela_id=nueva.id, tipo_pieza="", prenda="", titulo=nombre_nueva[:160],
            empleada_code=j.empleada_code, empleada_nombre=j.empleada_nombre,
            total_tallas=len(paso["mueven"]), iniciada_at=j.iniciada_at, terminada_at=j.terminada_at,
            revisada_at=j.revisada_at, revisada_por=j.revisada_por, notas=j.notas,
        )
        session.add(j2)
        session.flush()
        for c in paso["mueven"]:
            c.jornada_id = j2.id
            c.escuela_id = nueva.id
            session.add(c)
        j.total_tallas = len(paso["quedan"])
        session.add(j)
    for c in session.scalars(select(ConteoInventario).where(ConteoInventario.escuela_id == vieja.id)).all():
        if c.variante_id in {v.id for p in plan["productos"] for v in p.variantes}:
            c.escuela_id = nueva.id
            session.add(c)
    if renombrar_vieja:
        vieja.nombre = renombrar_vieja
        session.add(vieja)
    session.flush()
    return nueva


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--escuela", type=int, required=True)
    parser.add_argument("--nivel", required=True)
    parser.add_argument("--nombre", required=True, help="nombre de la escuela nueva (la que se lleva ese nivel)")
    parser.add_argument("--renombrar-vieja", default=None)
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args(argv)
    with get_session() as session:
        plan = planear(session, escuela_id=args.escuela, nivel=args.nivel, nombre_nueva=args.nombre)
        print(f"{plan['vieja'].nombre!r} → se lleva {plan['nivel'].nombre} a {args.nombre!r}" + (f" y la vieja pasa a {args.renombrar_vieja!r}" if args.renombrar_vieja else ""))
        for p in plan["productos"]:
            print(f"  se va  #{p.id:3} {p.nombre_base}")
        for p in plan["se_quedan"]:
            print(f"  queda  #{p.id:3} {p.nombre_base}")
        for paso in plan["jornadas"]:
            j = paso["jornada"]
            if paso["mueven"]:
                print(f"  jornada #{j.id} ({j.empleada_nombre}, {j.iniciada_at:%d/%m}): {len(paso['mueven'])} tallas se van" + (f", {len(paso['quedan'])} se quedan → se parte en dos" if paso["quedan"] else " → se va completa"))
        if not args.aplicar:
            print("\nSolo fue un vistazo. Con --aplicar se separa de verdad.")
            return 0
        nueva = aplicar(session, plan, nombre_nueva=args.nombre, renombrar_vieja=args.renombrar_vieja)
        session.commit()
        print(f"\nListo: escuela #{nueva.id} {nueva.nombre!r} con {len(plan['productos'])} prendas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
