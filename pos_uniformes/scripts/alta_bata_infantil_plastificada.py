"""Alta puntual: producto "Bata Infantil Plastificada" a $75.

Crea el producto (si no existe) y una variante talla 'Uni' por cada color,
con stock 0 (se cuenta después). Es idempotente: se puede correr varias veces.

    python pos_uniformes/scripts/alta_bata_infantil_plastificada.py
"""
from decimal import Decimal

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Producto, Variante
from sqlalchemy import Integer, func, select

NOMBRE = "Bata Infantil Plastificada"
PRECIO = Decimal("75.00")
COLORES = [
    "Rojo",
    "Rosa",
    "Amarillo",
    "Vino",
    "Azul Marino",
    "Verde",
    "Blanca",
    "Azul cielo",
]
TALLA = "Uni"

# Mismos catálogos que el resto de las batas infantiles (producto 51/57)
CATEGORIA_ID = 1      # Accesorio
MARCA_ID = 1          # Sin marca
TIPO_PRENDA_ID = 1    # Accesorio
TIPO_PIEZA_ID = 1     # Bata
ATRIBUTO_ID = 5       # Infantil
GENERO = "Unisex"


def siguiente_sku(session) -> int:
    n = session.execute(
        select(func.max(func.cast(func.substring(Variante.sku, 4), Integer)))
        .where(Variante.sku.op("~")("^SKU[0-9]+$"))
    ).scalar()
    return int(n or 0)


def main() -> None:
    with get_session() as session:
        producto = session.execute(
            select(Producto).where(Producto.marca_id == MARCA_ID, Producto.nombre == NOMBRE)
        ).scalar_one_or_none()

        if producto is None:
            producto = Producto(
                categoria_id=CATEGORIA_ID,
                marca_id=MARCA_ID,
                nombre=NOMBRE,
                nombre_base=NOMBRE,
                descripcion=None,
                activo=True,
                tipo_prenda_id=TIPO_PRENDA_ID,
                tipo_pieza_id=TIPO_PIEZA_ID,
                atributo_id=ATRIBUTO_ID,
                genero=GENERO,
            )
            session.add(producto)
            session.flush()
            print(f"Producto creado: id={producto.id} · {NOMBRE}")
        else:
            print(f"Producto ya existía: id={producto.id} · {NOMBRE}")

        existentes = {
            (v.talla, v.color): v
            for v in session.execute(
                select(Variante).where(Variante.producto_id == producto.id)
            ).scalars()
        }

        n = siguiente_sku(session)
        for color in COLORES:
            v = existentes.get((TALLA, color))
            if v is not None:
                v.precio_venta = PRECIO
                print(f"  = {v.sku} {color} (ya existía, precio → ${PRECIO})")
                continue
            n += 1
            sku = f"SKU{n:06d}"
            session.add(
                Variante(
                    producto_id=producto.id,
                    sku=sku,
                    talla=TALLA,
                    color=color,
                    precio_venta=PRECIO,
                    stock_actual=0,
                    activo=True,
                    origen_legacy=False,
                    disponibilidad_oculta=False,
                )
            )
            print(f"  + {sku} {TALLA} {color} ${PRECIO}")

        session.commit()
        print("Listo.")


if __name__ == "__main__":
    main()
