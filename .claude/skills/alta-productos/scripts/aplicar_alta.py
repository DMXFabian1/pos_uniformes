#!/usr/bin/env python3
"""Da de alta un producto con sus tallas por el camino oficial (CatalogService).

Por defecto es ENSAYO: hace todo dentro de una transacción, imprime lo que
quedaría (incluidos los SKU asignados) y hace ROLLBACK. Solo con --aplicar
hace COMMIT. Las validaciones son las del POS (admin, nombre duplicado, SKU).

Uso (desde la raíz del repo):
    python .claude/skills/alta-productos/scripts/aplicar_alta.py alta.json            # ensayo
    python .claude/skills/alta-productos/scripts/aplicar_alta.py alta.json --aplicar  # guarda
    ... --db-url postgresql+psycopg://...   # si no, usa la config del proyecto

alta.json (los nombres de catálogo deben EXISTIR tal cual; no se crean aquí):
{
  "producto": {
    "nombre": "Pants 2pz Deportivo",        # SIN la escuela: el POS la agrega
    "categoria": "Deportivo", "marca": "Sin marca",
    "escuela": "Técnica 18 (San Bartolo)",   # o null para producto general
    "tipo_prenda": "Deportivo", "tipo_pieza": "Pants 2pz",
    "nivel_educativo": "Secundaria", "atributo": "Deportivo",
    "genero": "Unisex", "escudo": "Con Escudo", "ubicacion": null, "descripcion": null
  },
  "color": "Sin color",
  "variantes": [{"talla": "10", "precio": 650}, {"talla": "12", "precio": 650}],
  "uniforme": {"grupo": "Deportivo", "orden": 2}   # opcional: liga la pieza nueva al uniforme
}

Solo ligar productos que YA existen (p. ej. piezas generales) al uniforme de una escuela:
{
  "escuela": "Ignacio Allende (Jaral)",
  "ligar_al_uniforme": [{"producto": "Falda Escoces", "grupo": "Diario", "orden": 9}]
}
("producto" y "ligar_al_uniforme" pueden ir juntos en el mismo spec.)
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--aplicar", action="store_true", help="hacer COMMIT (sin esto: ensayo con ROLLBACK)")
    ap.add_argument("--db-url")
    args = ap.parse_args()

    from sqlalchemy import create_engine, select
    from sqlalchemy.exc import ProgrammingError
    from sqlalchemy.orm import Session

    from pos_uniformes.database.models import (
        AtributoProducto, Categoria, Escuela, Marca, NivelEducativo, Producto, RolUsuario,
        TipoPieza, TipoPrenda, Usuario,
    )
    from pos_uniformes.services import uniforme_service
    from pos_uniformes.services.catalog_service import CatalogService
    from pos_uniformes.utils.config import settings

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    prod = spec.get("producto")
    color = (spec.get("color") or "Sin color").strip()
    variantes = spec.get("variantes") or []
    ligar = spec.get("ligar_al_uniforme") or []
    if prod and not variantes:
        print("ERROR: el spec trae producto pero no variantes.")
        return 2
    if not prod and not ligar:
        print("ERROR: el spec no trae 'producto' ni 'ligar_al_uniforme'.")
        return 2

    engine = create_engine(args.db_url or settings.database_url, connect_args={"connect_timeout": 5})
    print(f"DB: {engine.url.host or 'local'}/{engine.url.database} · modo {'APLICAR (commit)' if args.aplicar else 'ENSAYO (rollback)'}")

    with Session(engine, autoflush=False, expire_on_commit=False) as session:
        def por_nombre(modelo, nombre, campo):
            if nombre in (None, ""):
                return None
            obj = session.scalar(select(modelo).where(modelo.nombre == nombre))
            if obj is None:
                raise SystemExit(f"ERROR: {campo} «{nombre}» no existe en el catálogo. "
                                 "Usar el valor existente (buscar_hermanos.py) o pedir a Daniel que lo cree.")
            return obj

        admin = session.scalar(
            select(Usuario).where(Usuario.rol == RolUsuario.ADMIN, Usuario.activo.is_(True)).limit(1)
        )
        if admin is None:
            print("ERROR: no hay usuario ADMIN activo.")
            return 2

        escuela = por_nombre(Escuela, (prod or {}).get("escuela") or spec.get("escuela"), "escuela")

        def ligar_pieza(producto, conf: dict) -> None:
            if escuela is None:
                raise SystemExit("ERROR: ligar al uniforme requiere escuela.")
            uni = uniforme_service.uniforme_de(session, escuela.id, crear=True)
            pieza = uniforme_service.agregar_pieza(
                session, uni.id, producto.id, grupo=conf.get("grupo"),
                obligatoria=bool(conf.get("obligatoria", True)), orden=conf.get("orden"),
            )
            print(f"Uniforme de {escuela.nombre}: «{producto.nombre}» en grupo «{pieza.grupo}», orden {pieza.orden}")

        try:
            if prod:
                categoria = por_nombre(Categoria, prod["categoria"], "categoría")
                marca = por_nombre(Marca, prod["marca"], "marca")
                if categoria is None or marca is None:
                    raise SystemExit("ERROR: categoría y marca son obligatorias.")
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
                print(f"\nProducto: «{producto.nombre}» (id {producto.id})")
                print(f"{'SKU':<12} {'Talla':<6} {'Color':<12} {'Precio':>8}")
                for v in variantes:
                    var = CatalogService.crear_variante(
                        session, admin, producto, v.get("sku"), str(v["talla"]),
                        v.get("color") or color, Decimal(str(v["precio"])),
                        costo_referencia=Decimal(str(v["costo"])) if v.get("costo") is not None else None,
                        stock_inicial=int(v.get("stock", 0)),
                    )
                    print(f"{var.sku:<12} {var.talla:<6} {var.color:<12} {var.precio_venta:>8}")

                if spec.get("uniforme"):
                    ligar_pieza(producto, spec["uniforme"])

            for conf in ligar:
                existente = session.scalar(select(Producto).where(Producto.nombre == conf["producto"]))
                if existente is None:
                    raise SystemExit(f"ERROR: producto «{conf['producto']}» no existe (nombre exacto).")
                ligar_pieza(existente, conf)
        except ValueError as exc:
            session.rollback()
            print(f"\nERROR del POS: {exc}")
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
            print("\nENSAYO: rollback, no se guardó nada. Los SKU reales pueden cambiar si alguien da de alta antes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
