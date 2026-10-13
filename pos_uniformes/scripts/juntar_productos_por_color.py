"""Junta varios productos «uno por color» en un solo producto (el modelo).

Ropa normal (Daniel, 2026-10-13): el producto es el modelo y las variantes son
talla × color. Las 16 «Camisa Manga Larga <Color>» se vuelven «Camisa Manga
Larga» con sus 229 variantes. Requiere que ya esté actualizado el código que
pone el color en el nombre cuando un producto tiene varios (commit 7630d4ed);
si no, etiquetas y tickets saldrían sin color.

Qué hace, en UNA transacción (o todo o nada):
1. Revisa que todos sean de la misma categoría, marca, línea, pieza, género y
   escuela, que no se repita ninguna talla × color y que el nombre nuevo no
   lo tenga otro producto.
2. Renombra el producto destino (CatalogService.actualizar_producto).
3. Mueve las variantes de los demás al destino. SKU, precio, existencias e
   historial NO cambian: todo cuelga del SKU. Cada movimiento queda en el
   historial del catálogo.
4. Apaga los productos que quedaron vacíos (no se borran).

Uso (sin --aplicar solo enseña lo que haría):
    python -m pos_uniformes.scripts.juntar_productos_por_color \\
        --destino 542 --origen 543,544,... --nombre "Camisa Manga Larga" [--aplicar]
"""

from __future__ import annotations

import argparse
from collections import Counter


class NoSePuede(Exception):
    pass


def juntar(session, *, destino_id: int, origen_ids: list[int], nombre: str, usuario) -> dict:
    from sqlalchemy import select

    from pos_uniformes.database.models import Producto, Variante
    from pos_uniformes.database.models import TipoCambioCatalogo, TipoEntidadCatalogo
    from pos_uniformes.services.catalog_service import CatalogService as C

    ids = [destino_id] + [i for i in origen_ids if i != destino_id]
    productos = [session.get(Producto, i) for i in ids]
    if any(p is None for p in productos):
        raise NoSePuede("Algún producto no existe.")
    destino = productos[0]

    def _clave(p):
        return (p.categoria_id, p.marca_id, p.tipo_prenda_id, p.tipo_pieza_id, p.escuela_id)

    distintos = {_clave(p) for p in productos}
    if len(distintos) != 1:
        raise NoSePuede(f"No son del mismo tipo (categoría/marca/línea/pieza/escuela): {distintos}")
    generos = {p.genero for p in productos[1:]}
    if len(generos) > 1 or (destino.genero and destino.genero not in generos):
        raise NoSePuede(f"Géneros distintos: {generos | {destino.genero}}")
    genero = destino.genero or next(iter(generos), None)
    variantes = [v for p in productos for v in p.variantes]
    repetidas = [k for k, n in Counter((v.talla.strip().casefold(), v.color.strip().casefold())
                                       for v in variantes).items() if n > 1]
    if repetidas:
        raise NoSePuede(f"Se repetirían talla×color: {repetidas[:5]}")
    ocupado = session.scalar(select(Producto).where(
        Producto.nombre == nombre, Producto.marca_id == destino.marca_id, Producto.id.notin_(ids)))
    if ocupado is not None:
        raise NoSePuede(f"Ya existe otro producto «{nombre}» (id {ocupado.id}).")

    antes = {
        "skus": sorted(v.sku for v in variantes),
        "stock": sum(int(v.stock_actual or 0) for v in variantes),
        "activas": sum(1 for v in variantes if v.activo),
    }

    C.actualizar_producto(
        session, usuario, destino, destino.categoria, destino.marca, nombre,
        descripcion=destino.descripcion, escuela=destino.escuela, tipo_prenda=destino.tipo_prenda,
        tipo_pieza=destino.tipo_pieza, nivel_educativo=destino.nivel_educativo,
        atributo=destino.atributo, genero=genero, escudo=destino.escudo,
        ubicacion=destino.ubicacion,
    )
    if not destino.activo:
        # El destino puede ser un modelo vacío que se dejó apagado (la
        # «Camisa Manga Larga» del 23-may): se vuelve a prender.
        C.cambiar_estado_producto(session, usuario, destino, True)
    movidas = 0
    for origen in productos[1:]:
        for v in list(origen.variantes):
            C._registrar_cambios(
                session=session, usuario=usuario, entidad_tipo=TipoEntidadCatalogo.PRESENTACION,
                entidad_id=v.id, descripcion_entidad=C._descripcion_presentacion(v),
                valores_anteriores={"producto_id": origen.id}, valores_nuevos={"producto_id": destino.id},
                accion_por_campo={"producto_id": TipoCambioCatalogo.ACTUALIZACION},
                observacion=f"Juntar «{origen.nombre}» en «{nombre}»",
            )
            v.producto_id = destino.id
            session.add(v)
            movidas += 1
        session.flush()
        session.expire(origen, ["variantes"])
        C.cambiar_estado_producto(session, usuario, origen, False)
    session.flush()
    session.expire_all()

    destino = session.get(Producto, destino_id)
    finales = list(session.scalars(select(Variante).where(Variante.producto_id == destino_id)).all())
    despues = {
        "skus": sorted(v.sku for v in finales),
        "stock": sum(int(v.stock_actual or 0) for v in finales),
        "activas": sum(1 for v in finales if v.activo),
    }
    if despues != antes:
        raise NoSePuede(f"Algo no cuadra (antes {antes['stock']}/{len(antes['skus'])}, "
                        f"después {despues['stock']}/{len(despues['skus'])}); no se aplicó nada.")
    return {"destino": destino.nombre, "variantes": len(finales), "movidas": movidas,
            "stock": despues["stock"], "apagados": len(productos) - 1,
            "colores": sorted({v.color for v in finales})}


def main() -> None:
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.database.models import Usuario

    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", type=int, required=True)
    ap.add_argument("--origen", required=True, help="ids separados por coma")
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    origen = [int(x) for x in a.origen.split(",") if x.strip()]
    with get_session() as s:
        try:
            r = juntar(s, destino_id=a.destino, origen_ids=origen, nombre=a.nombre, usuario=s.get(Usuario, 1))
        except NoSePuede as exc:
            s.rollback()
            print("NO SE HIZO NADA:", exc)
            raise SystemExit(1)
        print(r)
        if a.aplicar:
            s.commit()
            print("APLICADO.")
        else:
            s.rollback()
            print("Prueba: no se guardó nada (usa --aplicar).")


if __name__ == "__main__":
    main()
