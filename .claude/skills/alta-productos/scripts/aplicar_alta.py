#!/usr/bin/env python3
"""Aplica un plan de catálogo por el camino oficial (CatalogService + uniforme_service).

TODO el plan va en UNA transacción: si algo falla, no se guarda nada, y en el
ensayo los SKU que se ven son los que de verdad quedarían.
Por defecto es ENSAYO (ROLLBACK). Solo con --aplicar hace COMMIT.

Uso (desde la raíz del repo):
    python .claude/skills/alta-productos/scripts/aplicar_alta.py plan.json [otro.json ...]
    ... --aplicar                       # guarda
    ... --env-file /ruta/pos_uniformes.env   # p. ej. la caja (ver CLAUDE.md)
    ... --db-url postgresql+psycopg://...

Cada archivo trae UN spec o una LISTA de specs. Un spec puede tener cualquiera
de estos bloques (los nombres de catálogo deben EXISTIR tal cual; aquí no se crean):

  Alta de producto nuevo:
  {"producto": {"nombre": "Pants 2pz Deportivo",          # SIN la escuela: el POS la agrega
                "categoria": "Deportivo", "marca": "Sin marca",
                "escuela": "Técnica 18 (San Bartolo)",     # o null para producto general
                "tipo_prenda": "Deportivo", "tipo_pieza": "Pants 2pz",
                "nivel_educativo": "Secundaria", "atributo": "Deportivo",
                "genero": "Unisex", "escudo": "Con Escudo", "ubicacion": null, "descripcion": null},
   "color": "Sin color",
   "variantes": [{"talla": "10", "precio": 650}, {"talla": "12", "precio": 650, "costo": 400}],
   "uniforme": {"grupo": "Deportivo", "orden": 2}}          # opcional

  Ligar productos que YA existen al uniforme de una escuela:
  {"escuela": "Ignacio Allende (Jaral)",
   "ligar_al_uniforme": [{"producto": "Falda Escoces", "grupo": "Diario", "orden": 9}]}

  (en "ligar_al_uniforme" y "editar" se puede usar "producto_id" en vez de "producto")

  Editar productos que YA existen (color de todas sus tallas y/o nombre):
  {"editar": [{"producto": "Chaleco Rojo Ignacio Allende (Jaral)",   # nombre completo actual
               "color": "Azul",                                     # opcional
               "nombre": "Chaleco Azul"}]}                          # opcional, SIN escuela

Al editar se conservan SKU, talla, precio, costo_referencia y stock_mínimo
(actualizar_variante los sobrescribe si no se le pasan) y todos los campos del
producto (actualizar_producto también).
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

import _comun


def leer_specs(rutas: list[Path]) -> list[dict]:
    specs: list[dict] = []
    for ruta in rutas:
        data = json.loads(ruta.read_text(encoding="utf-8"))
        specs.extend(data if isinstance(data, list) else [data])
    return specs


def validar(spec: dict, i: int) -> None:
    if not any(spec.get(k) for k in ("producto", "ligar_al_uniforme", "editar")):
        raise SystemExit(f"ERROR: el spec #{i} no trae 'producto', 'ligar_al_uniforme' ni 'editar'.")
    if spec.get("producto") and not spec.get("variantes"):
        raise SystemExit(f"ERROR: el spec #{i} trae producto pero no variantes.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("specs", type=Path, nargs="+")
    ap.add_argument("--aplicar", action="store_true", help="hacer COMMIT (sin esto: ensayo con ROLLBACK)")
    _comun.agregar_argumentos_db(ap)
    args = ap.parse_args()

    specs = leer_specs(args.specs)
    for i, spec in enumerate(specs, 1):
        validar(spec, i)

    engine = _comun.motor(args)
    print(f"Modo: {'APLICAR (commit)' if args.aplicar else 'ENSAYO (rollback)'} · {len(specs)} spec(s) en una transacción")

    from sqlalchemy import select
    from sqlalchemy.exc import ProgrammingError
    from sqlalchemy.orm import Session

    from pos_uniformes.database.models import (
        AtributoProducto, Categoria, Escuela, Marca, NivelEducativo, Producto, RolUsuario,
        TipoPieza, TipoPrenda, Usuario, Variante,
    )
    from pos_uniformes.services import uniforme_service
    from pos_uniformes.services.catalog_service import CatalogService

    with Session(engine, autoflush=False, expire_on_commit=False) as session:
        def por_nombre(modelo, nombre, campo):
            if nombre in (None, ""):
                return None
            obj = session.scalar(select(modelo).where(modelo.nombre == nombre))
            if obj is None:
                raise SystemExit(f"ERROR: {campo} «{nombre}» no existe en el catálogo. "
                                 "Usar el valor existente (buscar_hermanos.py) o pedir a Daniel que lo cree. "
                                 "No se guardó nada.")
            return obj

        def producto_existente(conf: dict):
            """Por `producto_id` si viene (sobrevive a un renombre en el mismo plan), si no por nombre exacto."""
            if conf.get("producto_id"):
                prod = session.get(Producto, int(conf["producto_id"]))
            else:
                prod = session.scalar(select(Producto).where(Producto.nombre == conf["producto"]))
            if prod is None:
                ref = conf.get("producto_id") or conf.get("producto")
                raise SystemExit(f"ERROR: producto «{ref}» no existe. No se guardó nada.")
            return prod

        admin = session.scalar(
            select(Usuario).where(Usuario.rol == RolUsuario.ADMIN, Usuario.activo.is_(True)).limit(1)
        )
        if admin is None:
            print("ERROR: no hay usuario ADMIN activo.")
            return 2

        def ligar_pieza(escuela, producto, conf: dict) -> None:
            if escuela is None:
                raise SystemExit("ERROR: ligar al uniforme requiere escuela. No se guardó nada.")
            uni = uniforme_service.uniforme_de(session, escuela.id, crear=True)
            pieza = uniforme_service.agregar_pieza(
                session, uni.id, producto.id, grupo=conf.get("grupo"),
                obligatoria=bool(conf.get("obligatoria", True)), orden=conf.get("orden"),
            )
            print(f"  uniforme {escuela.nombre}: + «{producto.nombre}» · {pieza.grupo} · orden {pieza.orden}")

        def editar(conf: dict) -> None:
            prod = producto_existente(conf)
            nuevo_nombre = (conf.get("nombre") or "").strip()
            if nuevo_nombre:
                escuela_nombre = prod.escuela.nombre if prod.escuela else ""
                if escuela_nombre and nuevo_nombre.endswith(escuela_nombre):
                    # actualizar_producto vuelve a pegar la escuela: quitarla evita «… X X».
                    nuevo_nombre = nuevo_nombre[: -len(escuela_nombre)].strip()
                antes = prod.nombre
                CatalogService.actualizar_producto(
                    session, admin, prod, prod.categoria, prod.marca, nuevo_nombre,
                    descripcion=prod.descripcion, escuela=prod.escuela, tipo_prenda=prod.tipo_prenda,
                    tipo_pieza=prod.tipo_pieza, nivel_educativo=prod.nivel_educativo,
                    atributo=prod.atributo, genero=prod.genero, escudo=prod.escudo,
                    ubicacion=prod.ubicacion,
                )
                print(f"\nEditar: «{antes}» → «{prod.nombre}»")
            else:
                print(f"\nEditar: «{prod.nombre}»")
            color = (conf.get("color") or "").strip()
            if color:
                variantes = session.scalars(
                    select(Variante).where(Variante.producto_id == prod.id, Variante.activo.is_(True))
                ).all()
                for v in sorted(variantes, key=lambda v: v.sku):
                    antes = v.color
                    CatalogService.actualizar_variante(
                        session, admin, v, prod, v.sku, v.talla, color, v.precio_venta,
                        costo_referencia=v.costo_referencia, stock_minimo=v.stock_minimo,
                    )
                    print(f"  {v.sku:<12} {v.talla:<5} {antes} → {v.color} · ${v.precio_venta:.0f} · stock {v.stock_actual}")

        try:
            for spec in specs:
                prod = spec.get("producto")
                escuela = por_nombre(Escuela, (prod or {}).get("escuela") or spec.get("escuela"), "escuela")

                for conf in spec.get("editar") or []:
                    editar(conf)

                if prod:
                    categoria = por_nombre(Categoria, prod["categoria"], "categoría")
                    marca = por_nombre(Marca, prod["marca"], "marca")
                    if categoria is None or marca is None:
                        raise SystemExit("ERROR: categoría y marca son obligatorias. No se guardó nada.")
                    producto = CatalogService.crear_producto(
                        session, admin, categoria, marca, prod["nombre"],
                        descripcion=prod.get("descripcion"),
                        escuela=escuela,
                        tipo_prenda=por_nombre(TipoPrenda, prod.get("tipo_prenda"), "tipo de prenda"),
                        tipo_pieza=por_nombre(TipoPieza, prod.get("tipo_pieza"), "tipo de pieza"),
                        nivel_educativo=por_nombre(NivelEducativo, prod.get("nivel_educativo"), "nivel"),
                        atributo=por_nombre(AtributoProducto, prod.get("atributo"), "atributo"),
                        genero=prod.get("genero"), escudo=prod.get("escudo"), ubicacion=prod.get("ubicacion"),
                    )
                    color = (spec.get("color") or "Sin color").strip()
                    print(f"\nAlta: «{producto.nombre}»")
                    for v in spec["variantes"]:
                        var = CatalogService.crear_variante(
                            session, admin, producto, v.get("sku"), str(v["talla"]),
                            v.get("color") or color, Decimal(str(v["precio"])),
                            costo_referencia=Decimal(str(v["costo"])) if v.get("costo") is not None else None,
                            stock_inicial=int(v.get("stock", 0)),
                        )
                        print(f"  {var.sku:<12} {var.talla:<5} {var.color:<12} ${var.precio_venta:.0f}")
                    if spec.get("uniforme"):
                        ligar_pieza(escuela, producto, spec["uniforme"])

                ligar = spec.get("ligar_al_uniforme") or []
                if ligar:
                    print()
                for conf in ligar:
                    ligar_pieza(escuela, producto_existente(conf), conf)
        except ValueError as exc:
            session.rollback()
            print(f"\nERROR del POS: {exc}\nNo se guardó nada.")
            return 1
        except ProgrammingError as exc:
            session.rollback()
            print(f"\nERROR: la base no coincide con el código de esta rama ({type(exc.orig).__name__}). "
                  "Probablemente le faltan migraciones (alembic upgrade head). No se guardó nada.")
            return 1

        if args.aplicar:
            session.commit()
            print("\nCOMMIT hecho. Quedó registro en cambio_catalogo.")
        else:
            session.rollback()
            print("\nENSAYO: rollback, no se guardó nada. Los SKU pueden correrse si alguien da de alta antes de aplicar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
