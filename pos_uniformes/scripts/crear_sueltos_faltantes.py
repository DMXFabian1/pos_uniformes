"""Catálogo, fase 3: el pants suelto que deja la chamarra.

Hay escuelas que venden chamarra pero no tienen su "Pants Suelto <escuela>"
en el catálogo, así que al vender una chamarra el pants que queda no tenía
dónde caer. Daniel (2026-09-22) decidió **crearlos**: mismas tallas que el
Pants 2pz de la escuela, stock 0 (sube solo cada vez que se vende una
chamarra), color el del 2pz, y el precio de siempre de los sueltos de escuela:

    tallas numéricas (2–18)  → $259
    tallas de letra (CH…EXG) → $269

Después, `armar_recetas --aplicar` les pone la receta a esas chamarras.
No toca ningún producto existente; solo da de alta los que faltan (con SKUs
nuevos de la secuencia, como cualquier alta del POS).

Uso:
  python -m pos_uniformes.scripts.crear_sueltos_faltantes            # dry-run
  python -m pos_uniformes.scripts.crear_sueltos_faltantes --aplicar
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

PRECIO_NUMERICA = Decimal("259.00")
PRECIO_LETRA = Decimal("269.00")


def precio_de(talla: str) -> Decimal:
    return PRECIO_NUMERICA if str(talla).strip().isdigit() else PRECIO_LETRA


def _producto_de(session, escuela_id: int, tipo_pieza: str) -> Producto | None:
    return session.scalars(
        select(Producto)
        .join(TipoPieza, TipoPieza.id == Producto.tipo_pieza_id)
        .where(Producto.escuela_id == int(escuela_id), TipoPieza.nombre == tipo_pieza, Producto.activo == True)  # noqa: E712
        .order_by(Producto.id)
    ).first()


def planear(session) -> list[dict]:
    """Una fila por chamarra de escuela que no tiene con qué dejar el suelto."""
    filas = []
    for chamarra in cs.conjuntos_activos(session):
        if cs._tipo_pieza(chamarra) != "Chamarra" or chamarra.escuela_id is None:
            continue
        if cs.receta_de(session, chamarra.id):
            continue
        # Solo las que de plano no tienen de dónde sacar el suelto. Si la escuela
        # usa un suelto general (Benito Juárez, Justo Sierra…), ese es el suyo y
        # no se le inventa otro: partiría el mismo montón en dos.
        if "Pants Suelto" not in (cs.proponer_receta(session, chamarra).get("faltan") or []):
            continue
        p2 = _producto_de(session, chamarra.escuela_id, "Pants 2pz")
        if p2 is None:
            continue
        variantes = session.scalars(
            select(Variante).where(Variante.producto_id == p2.id, Variante.activo == True)  # noqa: E712
        ).all()
        if not variantes:
            continue
        filas.append({
            "escuela": chamarra.escuela,
            "chamarra": chamarra,
            "pants2": p2,
            "nombre": f"Pants Suelto {chamarra.escuela.nombre}",
            "tallas": [(str(v.talla), str(v.color or "Sin color")) for v in variantes],
        })
    return filas


def imprimir(filas: list[dict], *, salida=sys.stdout) -> int:
    total = 0
    for f in filas:
        tallas = ", ".join(t for t, _c in f["tallas"])
        total += len(f["tallas"])
        print(f"+ {f['nombre']}  ({len(f['tallas'])} tallas: {tallas})", file=salida)
        print(f"    de {f['pants2'].nombre}; color {f['tallas'][0][1]}; $259 numéricas / $269 letra", file=salida)
    print(f"\n{len(filas)} productos nuevos, {total} tallas.", file=salida)
    return total


def aplicar(session, filas: list[dict], usuario: Usuario) -> tuple[int, int]:
    productos = tallas = 0
    for f in filas:
        p2 = f["pants2"]
        producto = CatalogService.crear_producto(
            session, usuario,
            categoria=p2.categoria, marca=p2.marca,
            nombre="Pants Suelto",
            escuela=f["escuela"],
            tipo_prenda=p2.tipo_prenda,
            tipo_pieza=session.scalars(select(TipoPieza).where(TipoPieza.nombre == "Pants Suelto")).first(),
            nivel_educativo=p2.nivel_educativo,
            genero=p2.genero,
            descripcion="El pants que queda al vender la chamarra.",
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
                precio_venta=precio_de(talla), stock_inicial=0,
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
