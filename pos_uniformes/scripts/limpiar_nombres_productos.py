"""Fase 1 del rediseño del catálogo: nombres limpios, sin "| Tipo | Pieza".

Hasta el 20/09 `Producto.nombre` cargaba la ficha: "Camisa Cuello olan
Blanca | Oficial | Camisa". El tipo de prenda y el de pieza ya viven en sus
campos, así que el sufijo solo estorbaba (nombres repetidos, "|" recortado
en cada pantalla, ruido en la búsqueda). Este script deja `nombre` limpio:

- Si hay `nombre_base` (el curado, sin "Ad Hoc" y con acentos), ese manda.
- Si no, el primer tramo antes del "|".
- Si el sufijo traía un tipo de prenda/pieza que el campo no tenía, se
  recupera al campo (no se pierde información).
- Si dos productos activos de la misma marca quedarían con el mismo nombre
  (hay UniqueConstraint marca+nombre), al segundo se le pone " (2)" y se avisa:
  seguramente es un duplicado que Daniel debe fundir.

Los SKUs no se tocan: viven en la talla y ya están impresos.

Uso:  python -m pos_uniformes.scripts.limpiar_nombres_productos [--aplicar]
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Producto, TipoPieza, TipoPrenda
from pos_uniformes.utils.product_name import sanitize_product_display_name


_CONECTORES = {"de", "del", "la", "las", "los", "el", "en", "y", "a", "con", "por", "para"}


def con_mayusculas(nombre: str) -> str:
    """Cada palabra con inicial mayúscula ("olan" → "Olan", "cielo" → "Cielo"),
    salvo conectores (de, del, y…). No toca lo que ya empieza en mayúscula
    ni las siglas (CBTIS, SABES, ESTV) ni "2pz"."""
    palabras = nombre.split()
    out = []
    for i, w in enumerate(palabras):
        if w[:1].islower() and not (i > 0 and w.lower() in _CONECTORES):
            w = w[0].upper() + w[1:]
        out.append(w)
    return " ".join(out)


def nombre_limpio(p: Producto) -> str:
    base = str(p.nombre_base or "").strip()
    if base and "|" not in base:
        return con_mayusculas(sanitize_product_display_name(base))
    return con_mayusculas(sanitize_product_display_name(str(p.nombre or "").split("|")[0]))


def planear(session) -> list[dict]:
    """[{producto, nuevo, tipo_prenda, tipo_pieza, choque}] de lo que cambiaría."""
    prendas = {t.nombre.strip().lower(): t for t in session.scalars(select(TipoPrenda)).all()}
    piezas = {t.nombre.strip().lower(): t for t in session.scalars(select(TipoPieza)).all()}
    productos = list(session.scalars(select(Producto).order_by(Producto.id)).all())
    plan = []
    vistos: dict[tuple[int, str], int] = {}   # (marca, nombre limpio) → id que lo tomó primero
    for p in productos:
        nuevo = nombre_limpio(p)
        sufijo = [x.strip() for x in str(p.nombre or "").split("|")[1:]]
        tp = next((prendas[x.lower()] for x in sufijo if x.lower() in prendas), None) if p.tipo_prenda_id is None else None
        tz = next((piezas[x.lower()] for x in sufijo if x.lower() in piezas), None) if p.tipo_pieza_id is None else None
        clave = (int(p.marca_id), nuevo.lower())
        choque = None
        if p.activo:
            if clave in vistos:
                choque = vistos[clave]
                n = 2
                while (int(p.marca_id), f"{nuevo} ({n})".lower()) in vistos:
                    n += 1
                nuevo = f"{nuevo} ({n})"
            vistos[(int(p.marca_id), nuevo.lower())] = int(p.id)
        if nuevo != (p.nombre or "") or tp is not None or tz is not None:
            plan.append({"producto": p, "nuevo": nuevo, "tipo_prenda": tp, "tipo_pieza": tz, "choque": choque})
    return plan


def aplicar(session, plan: list[dict]) -> int:
    # Dos pasadas: primero un nombre temporal, para que el UNIQUE (marca,
    # nombre) no choque a medio camino (a toma el nombre que b todavía tiene).
    for paso in plan:
        p = paso["producto"]
        p.nombre = f"__limpiando_{p.id}__"
        session.add(p)
    session.flush()
    for paso in plan:
        p = paso["producto"]
        p.nombre = paso["nuevo"]
        if p.nombre_base and "|" not in p.nombre_base:
            p.nombre_base = con_mayusculas(sanitize_product_display_name(p.nombre_base))
        if paso["tipo_prenda"] is not None:
            p.tipo_prenda_id = paso["tipo_prenda"].id
        if paso["tipo_pieza"] is not None:
            p.tipo_pieza_id = paso["tipo_pieza"].id
        session.add(p)
    session.flush()
    return len(plan)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="sin esto solo enseña")
    args = parser.parse_args(argv)
    with get_session() as session:
        plan = planear(session)
        if not plan:
            print("Nada que limpiar: todos los nombres ya están sin sufijo.")
            return 0
        recuperados = [x for x in plan if x["tipo_prenda"] or x["tipo_pieza"]]
        choques = [x for x in plan if x["choque"]]
        for x in plan[:25]:
            p = x["producto"]
            print(f"  #{p.id:4} {str(p.nombre)[:58]!r:60} → {x['nuevo']!r}")
        if len(plan) > 25:
            print(f"  … y {len(plan) - 25} más")
        print(f"\n{len(plan)} productos cambian de nombre.")
        for x in recuperados:
            print(f"  campo recuperado del sufijo: #{x['producto'].id} " + ", ".join(f"{k}={v.nombre}" for k, v in (("tipo_prenda", x["tipo_prenda"]), ("tipo_pieza", x["tipo_pieza"])) if v))
        for x in choques:
            print(f"  ⚠ CHOQUE: #{x['producto'].id} quedaría igual que #{x['choque']} → se llama {x['nuevo']!r}. Revisa si es un duplicado para fundirlo.")
        if not args.aplicar:
            print("\nSolo fue un vistazo. Con --aplicar se cambian de verdad (después: Meilisearch → Sincronizar).")
            return 0
        n = aplicar(session, plan)
        session.commit()
        print(f"\nListo: {n} nombres limpios. Sincroniza Meilisearch (Ctrl+Shift+A → Conteos/Meilisearch) para que la búsqueda los tome.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
