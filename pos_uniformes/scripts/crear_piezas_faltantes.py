"""Catálogo, fase 3: las prendas que un conjunto necesita y la escuela no tiene.

- La escuela vende **chamarra** pero no tiene su "Pants Suelto <escuela>": al
  venderla, el pants que queda no tenía dónde caer.
- La escuela vende **Pants 3pz** pero no tiene playera propia (Vicente
  Guerrero): el conjunto no sabe qué playera se lleva.

Daniel (2026-09-22) decidió crearlas. Mismas tallas y color que el Pants 2pz
de la escuela, stock 0 (sube o baja solo con las ventas del conjunto), y el
precio de siempre de esa prenda en las demás escuelas:

    Pants Suelto     numéricas $259 · letra $269
    Playera Deportiva numéricas $199 (12–18: $209) · CH $219 · MD $225 · GD $235 · EXG $239

Después, `armar_recetas --aplicar` les pone la receta a esos conjuntos.
No toca ningún producto existente; solo da de alta los que faltan (con SKUs
nuevos de la secuencia, como cualquier alta del POS).

Uso:
  python -m pos_uniformes.scripts.crear_piezas_faltantes            # dry-run
  python -m pos_uniformes.scripts.crear_piezas_faltantes --aplicar
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    Producto,
    RolUsuario,
    TipoPieza,
    Usuario,
    Variante,
)
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.services import conjunto_service as cs
from pos_uniformes.services import uniforme_service as us

# El precio más común de esa prenda en las demás escuelas, por talla.
PRECIOS = {
    "Pants Suelto": {"numerica": Decimal("259.00"), "letra": {"CH": Decimal("269.00"), "MD": Decimal("269.00"), "GD": Decimal("269.00"), "EXG": Decimal("269.00")}},
    "Playera": {
        "numerica": Decimal("199.00"), "numerica_grande": Decimal("209.00"),
        "letra": {"CH": Decimal("219.00"), "MD": Decimal("225.00"), "GD": Decimal("235.00"), "EXG": Decimal("239.00")},
    },
}

# Qué se le crea a un conjunto al que le falta una pieza, y cómo se llama.
A_CREAR = {("Chamarra", "Pants Suelto"): "Pants Suelto", ("Pants 3pz", "Playera"): "Playera Deportiva"}


def precio_de(tipo_pieza: str, talla: str) -> Decimal:
    tabla = PRECIOS[tipo_pieza]
    t = str(talla).strip().upper()
    if t.isdigit():
        grande = tabla.get("numerica_grande")
        return grande if grande is not None and int(t) >= 12 else tabla["numerica"]
    return tabla["letra"].get(t, list(tabla["letra"].values())[-1])


def _producto_de(session, escuela_id: int, tipo_pieza: str) -> Producto | None:
    return session.scalars(
        select(Producto)
        .join(TipoPieza, TipoPieza.id == Producto.tipo_pieza_id)
        .where(Producto.escuela_id == int(escuela_id), TipoPieza.nombre == tipo_pieza, Producto.activo == True)  # noqa: E712
        .order_by(Producto.id)
    ).first()


def planear(session) -> list[dict]:
    """Una fila por pieza que hay que dar de alta para que un conjunto de esa
    escuela sepa de dónde sale (o dónde deja) su prenda."""
    filas = []
    for conjunto in cs.conjuntos_activos(session):
        tipo_conjunto = cs._tipo_pieza(conjunto)
        if conjunto.escuela_id is None or cs.receta_de(session, conjunto.id):
            continue
        # Solo lo que de plano no existe. Si la escuela usa una prenda general
        # (Benito Juárez con el suelto de punto), esa es la suya y no se le
        # inventa otra: partiría el mismo montón en dos.
        faltan = cs.proponer_receta(session, conjunto).get("faltan") or []
        for tipo_pieza in faltan:
            nombre_base = A_CREAR.get((tipo_conjunto, tipo_pieza))
            if nombre_base is None:
                continue
            p2 = _producto_de(session, conjunto.escuela_id, "Pants 2pz")
            if p2 is None:
                continue
            variantes = session.scalars(
                select(Variante).where(Variante.producto_id == p2.id, Variante.activo == True)  # noqa: E712
            ).all()
            if not variantes:
                continue
            filas.append({
                "escuela": conjunto.escuela,
                "conjunto": conjunto,
                "pants2": p2,
                "tipo_pieza": tipo_pieza,
                "nombre_base": nombre_base,
                "nombre": f"{nombre_base} {conjunto.escuela.nombre}",
                "tallas": [(str(v.talla), str(v.color or "Sin color")) for v in variantes],
            })
    return filas


def imprimir(filas: list[dict], *, salida=sys.stdout) -> int:
    total = 0
    for f in filas:
        tallas = ", ".join(t for t, _c in f["tallas"])
        total += len(f["tallas"])
        precios = ", ".join(f"{t} ${int(precio_de(f['tipo_pieza'], t))}" for t, _c in f["tallas"][:3])
        print(f"+ {f['nombre']}  ({len(f['tallas'])} tallas: {tallas})", file=salida)
        print(f"    para {f['conjunto'].nombre}; tallas y color de {f['pants2'].nombre}; {precios}…", file=salida)
    print(f"\n{len(filas)} productos nuevos, {total} tallas.", file=salida)
    return total


def aplicar(session, filas: list[dict], usuario: Usuario) -> tuple[int, int]:
    productos = tallas = 0
    for f in filas:
        p2 = f["pants2"]
        producto = CatalogService.crear_producto(
            session, usuario,
            categoria=p2.categoria, marca=p2.marca,
            nombre=f["nombre_base"],
            escuela=f["escuela"],
            tipo_prenda=p2.tipo_prenda,
            tipo_pieza=session.scalars(select(TipoPieza).where(TipoPieza.nombre == f["tipo_pieza"])).first(),
            nivel_educativo=p2.nivel_educativo,
            genero=p2.genero,
            descripcion=f"Pieza de {f['conjunto'].nombre}.",
        )
        productos += 1
        # Si la escuela ya tiene su uniforme armado, el suelto es una pieza más
        # (grupo Deportivo, junto al 2pz del que sale).
        uni = us.uniforme_de(session, f["escuela"].id)
        if uni is not None:
            us.agregar_pieza(session, uni.id, producto.id, grupo="Deportivo")
        for talla, color in f["tallas"]:
            CatalogService.crear_variante(
                session, usuario, producto=producto, sku=None, talla=talla, color=color,
                precio_venta=precio_de(f["tipo_pieza"], talla), stock_inicial=0,
            )
            tallas += 1
    return productos, tallas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aplicar", action="store_true", help="da de alta los productos; sin esto solo muestra")
    ap.add_argument("--usuario", default="", help="username ADMIN que queda como autor (por defecto, el primero)")
    args = ap.parse_args(argv)

    with get_session() as session:
        filas = planear(session)
        imprimir(filas)
        if not args.aplicar:
            print("\nDry-run. Agrega --aplicar para darlos de alta.")
            return 0
        if not filas:
            return 0
        q = select(Usuario).where(Usuario.rol == RolUsuario.ADMIN, Usuario.activo == True)  # noqa: E712
        if args.usuario:
            q = q.where(Usuario.username == args.usuario)
        usuario = session.scalars(q.order_by(Usuario.id)).first()
        if usuario is None:
            print("No hay un usuario ADMIN activo para firmar el alta.")
            return 1
        productos, tallas = aplicar(session, filas, usuario)
        session.commit()
        print(f"Aplicado: {productos} productos nuevos con {tallas} tallas (stock 0). Ahora corre armar_recetas --aplicar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
