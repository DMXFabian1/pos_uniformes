"""Alta puntual: producto "Calceta Corazón Blanca" a $49.

Las mismas tallas, precio y catálogos que la Calceta Escolar Blanca (producto
10); lo único distinto es el atributo: «Corazón» en vez de «Escolar». Se crea
el atributo si no existe, igual que «Chazarilla» en su día.

Es idempotente: se puede correr varias veces sin duplicar nada.

    python -m pos_uniformes.scripts.alta_calceta_corazon_blanca
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

NOMBRE = "Calceta Corazón Blanca"
PRECIO = Decimal("49.00")
COLOR = "Blanca"
#: Las mismas de la Calceta Escolar Blanca, en el mismo orden.
TALLAS = ["0-0", "0-2", "3-5", "6-8", "9-12", "13-18"]
ATRIBUTO = "Corazón"

# Mismos catálogos que el resto de las calcetas (producto 10).
CATEGORIA_ID = 1      # Accesorio
MARCA_ID = 1          # Sin marca
TIPO_PRENDA_ID = 1    # Accesorio
TIPO_PIEZA_ID = 3     # Calceta
GENERO = "Mujer"


def siguiente_sku(session) -> int:
    """El número más alto usado, leyendo los SKU que existen.

    Se calcula así y no con la tabla de secuencia a propósito: es el mismo
    camino que usó el alta anterior y no deja la secuencia desincronizada si
    alguien creó variantes por otro lado."""
    from sqlalchemy import Integer, func, select

    from pos_uniformes.database.models import Variante

    n = session.execute(
        select(func.max(func.cast(func.substring(Variante.sku, 4), Integer)))
        .where(Variante.sku.op("~")("^SKU[0-9]+$"))
    ).scalar()
    return int(n or 0)


def main() -> int:
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.database.models import AtributoProducto, Producto, Variante

    with get_session() as session:
        atributo = session.query(AtributoProducto).filter(
            AtributoProducto.nombre == ATRIBUTO
        ).first()
        if atributo is None:
            atributo = AtributoProducto(nombre=ATRIBUTO, activo=True)
            session.add(atributo)
            session.flush()
            print(f"Atributo «{ATRIBUTO}» creado (id {atributo.id}).")

        producto = session.query(Producto).filter(Producto.nombre == NOMBRE).first()
        if producto is None:
            producto = Producto(
                nombre=NOMBRE,
                nombre_base=NOMBRE,
                categoria_id=CATEGORIA_ID,
                marca_id=MARCA_ID,
                tipo_prenda_id=TIPO_PRENDA_ID,
                tipo_pieza_id=TIPO_PIEZA_ID,
                atributo_id=atributo.id,
                genero=GENERO,
                activo=True,
            )
            session.add(producto)
            session.flush()
            print(f"Producto «{NOMBRE}» creado (id {producto.id}).")
        else:
            print(f"El producto «{NOMBRE}» ya existía (id {producto.id}).")

        ya = {v.talla for v in session.query(Variante).filter(
            Variante.producto_id == producto.id
        ).all()}
        n = siguiente_sku(session)
        creadas = 0
        for talla in TALLAS:
            if talla in ya:
                continue
            n += 1
            session.add(Variante(
                producto_id=producto.id,
                sku=f"SKU{n:06d}",
                talla=talla,
                color=COLOR,
                precio_venta=PRECIO,
                stock_actual=0,      # se cuenta después
            ))
            creadas += 1
        session.commit()
        print(f"{creadas} talla(s) nueva(s). Total: {len(ya) + creadas} de {len(TALLAS)}.")
        print("Stock en 0: hay que contarlas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
