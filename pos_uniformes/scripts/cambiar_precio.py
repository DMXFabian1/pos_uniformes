"""Cambia el precio de venta de una prenda, en todas sus tallas o en algunas.

Toca **solo** el precio: no renombra, no regenera SKUs, no mueve existencia.
Para eso está el Catálogo del POS, que además pide usuario; esto es para el
cambio de a de veras (una prenda, un precio) sin abrir cinco diálogos.

Uso:
    # Ver qué cambiaría (no toca nada):
    python -m pos_uniformes.scripts.cambiar_precio --prenda "Pants 3pz Deportivo UVEG" --precio 750

    # Hacerlo:
    python -m pos_uniformes.scripts.cambiar_precio --prenda "Pants 3pz Deportivo UVEG" --precio 750 --aplicar

    # Solo algunas tallas:
    ... --prenda "..." --precio 750 --tallas CH,MD,GD --aplicar

La prenda se busca por nombre (basta un pedazo). Si empata con más de una, las
enseña y no toca nada: mejor quedarse quieto que adivinar cuál era.

Después de cambiar precios, el POS y el kiosko se re-indexan solos al abrir
(o Ctrl+Shift+A → Sincronizar si están abiertos).
"""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Escuela, Producto, Variante


def buscar_prendas(session, texto: str) -> list[Producto]:
    return list(
        session.scalars(
            select(Producto)
            .where(Producto.activo.is_(True), Producto.nombre_base.ilike(f"%{texto.strip()}%"))
            .order_by(Producto.nombre_base)
        ).all()
    )


def tallas_de(session, producto: Producto, tallas: set[str] | None) -> list[Variante]:
    vs = list(
        session.scalars(
            select(Variante).where(
                Variante.producto_id == producto.id, Variante.activo.is_(True)
            )
        ).all()
    )
    if tallas:
        pedidas = {t.strip().upper() for t in tallas}
        vs = [v for v in vs if str(v.talla).strip().upper() in pedidas]
    return sorted(vs, key=lambda v: str(v.talla))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cambia el precio de venta de una prenda.")
    parser.add_argument("--prenda", required=True, help="nombre o pedazo del nombre")
    parser.add_argument("--precio", required=True, help="el precio nuevo, p. ej. 750")
    parser.add_argument("--tallas", default="", help="solo estas, separadas por coma")
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args(argv)

    try:
        nuevo = Decimal(str(args.precio).replace(",", "").replace("$", ""))
    except InvalidOperation:
        print(f"'{args.precio}' no es un precio.")
        return 1
    if nuevo < 0:
        print("El precio no puede ser negativo.")
        return 1

    pedidas = {t for t in args.tallas.split(",") if t.strip()} or None

    with get_session() as session:
        prendas = buscar_prendas(session, args.prenda)
        if not prendas:
            print(f"No encontré ninguna prenda activa que diga '{args.prenda}'.")
            return 1
        if len(prendas) > 1:
            print(f"'{args.prenda}' empata con {len(prendas)} prendas. Sé más específico:")
            for p in prendas:
                esc = session.get(Escuela, p.escuela_id).nombre if p.escuela_id else "general"
                print(f"   #{p.id}  {p.nombre_base}   [{esc}]")
            return 1

        prenda = prendas[0]
        escuela = session.get(Escuela, prenda.escuela_id).nombre if prenda.escuela_id else "general"
        variantes = tallas_de(session, prenda, pedidas)
        if not variantes:
            print(f"{prenda.nombre_base}: no hay tallas activas que cambiar.")
            return 1

        print(f"#{prenda.id}  {prenda.nombre_base}   [{escuela}]\n")
        cambian = 0
        for v in variantes:
            antes = Decimal(str(v.precio_venta))
            if antes == nuevo:
                print(f"   {v.sku:<12} talla {str(v.talla):<5} ${antes:>8,.2f}   (ya estaba)")
                continue
            cambian += 1
            print(f"   {v.sku:<12} talla {str(v.talla):<5} ${antes:>8,.2f}  →  ${nuevo:>8,.2f}")
            if args.aplicar:
                v.precio_venta = nuevo
                session.add(v)

        if not args.aplicar:
            print(f"\nSolo reporte: {cambian} talla(s) cambiarían. Para hacerlo: --aplicar")
            return 0

        session.commit()
        print(f"\nListo: {cambian} talla(s) con precio nuevo.")
        print("El POS y el kiosko se re-indexan al abrir (o Ctrl+Shift+A → Sincronizar).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
