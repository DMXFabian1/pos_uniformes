"""Alta puntual: ropa normal de la nota 0008952 de Mios (Uriangato, 19/oct/2026).

Crea los 10 productos como ropa normal (categoria "Ropa casual", Unitalla),
con SKU automatico, precio de venta y costo, y registra la compra al proveedor
Mios para que el stock entre con movimiento ENTRADA_COMPRA.

Por defecto solo muestra lo que haria. Para guardar:
    python -m pos_uniformes.scripts.alta_compra_mios_0008952 --usuario admin --aplicar
"""
from __future__ import annotations

import argparse
from decimal import Decimal

from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Categoria, Compra, Marca, Producto, Proveedor, Usuario
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.services.compra_service import CompraItemInput, CompraService

CATEGORIA = "Ropa casual"
PROVEEDOR = "Mios"
NUMERO_DOCUMENTO = "MIOS-0008952"
TALLA = "Unitalla"
COLOR = "Sin color"

# (nombre, marca, cantidad, costo, precio_venta)
PRODUCTOS = [
    ("Leggings S01", "Showey", 288, "34", "89"),
    ("Sudadera KY357H", "Yamo", 40, "55", "99"),
    ("Blusa Cuello SY100", "Mios", 40, "29", "69"),
    ("Blusa Termica SY101", "Mios", 40, "29", "69"),
    ("Sudadera QS227", "Yamo", 50, "71", "139"),
    ("YT0572", "Darong", 30, "59", "99"),
    ("Sudadera MO194", "Mios", 24, "75", "149"),
    ("Sudadera C07", "Showey", 10, "86", "159"),
    ("Leggings MPP94", "Bethel", 40, "49", "99"),
    ("Pants J969R", "ABC", 8, "109", "199"),
]


def _get_or_create_categoria(session, usuario: Usuario) -> Categoria:
    categoria = session.scalar(select(Categoria).where(Categoria.nombre == CATEGORIA))
    return categoria or CatalogService.crear_categoria(session, usuario, CATEGORIA)


def _get_or_create_marca(session, usuario: Usuario, nombre: str) -> Marca:
    marca = session.scalar(select(Marca).where(Marca.nombre == nombre))
    return marca or CatalogService.crear_marca(session, usuario, nombre)


def _get_or_create_proveedor(session) -> Proveedor:
    proveedor = session.scalar(select(Proveedor).where(Proveedor.nombre == PROVEEDOR))
    if proveedor is None:
        proveedor = Proveedor(nombre=PROVEEDOR, direccion="Leovino Zavala No 176, Uriangato, Gto.")
        session.add(proveedor)
        session.flush()
    return proveedor


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usuario", required=True, help="username ADMIN que registra el alta")
    parser.add_argument("--aplicar", action="store_true", help="guardar cambios (sin esto solo simula)")
    args = parser.parse_args()

    with get_session() as session:
        usuario = session.scalar(select(Usuario).where(Usuario.username == args.usuario))
        if usuario is None:
            raise SystemExit(f"No existe el usuario '{args.usuario}'.")
        if session.scalar(select(Compra).where(Compra.numero_documento == NUMERO_DOCUMENTO)):
            raise SystemExit(f"La compra {NUMERO_DOCUMENTO} ya estaba registrada. No se hizo nada.")

        categoria = _get_or_create_categoria(session, usuario)
        items: list[CompraItemInput] = []
        for nombre, marca_nombre, cantidad, costo, precio in PRODUCTOS:
            marca = _get_or_create_marca(session, usuario, marca_nombre)
            existente = session.scalar(
                select(Producto).where(Producto.nombre == nombre, Producto.marca_id == marca.id)
            )
            if existente is not None:
                raise SystemExit(f"Ya existe '{nombre}' de {marca_nombre}. Revisa antes de volver a correr.")
            producto = CatalogService.crear_producto(
                session,
                usuario,
                categoria=categoria,
                marca=marca,
                nombre=nombre,
                descripcion=f"Compra Mios nota 0008952 (19/oct/2026), costo ${costo}.",
            )
            # crear_producto aplica title case; conservamos el codigo del proveedor en mayusculas.
            producto.nombre = producto.nombre_base = nombre
            variante = CatalogService.crear_variante(
                session,
                usuario,
                producto=producto,
                sku=None,
                talla=TALLA,
                color=COLOR,
                precio_venta=Decimal(precio),
                costo_referencia=Decimal(costo),
            )
            items.append(CompraItemInput(variante.id, cantidad, Decimal(costo)))
            print(f"  {variante.sku}  {producto.nombre:<22} {marca_nombre:<7} {cantidad:>4} pzas  costo ${costo:>4}  venta ${precio:>4}")

        compra = CompraService.crear_borrador(
            session,
            proveedor=_get_or_create_proveedor(session),
            usuario=usuario,
            numero_documento=NUMERO_DOCUMENTO,
            items=items,
            observacion="Nota 0008952 Mios Uriangato, 19/oct/2026.",
        )
        session.flush()
        CompraService.confirmar_compra(session, compra)
        session.flush()
        print(f"Compra {NUMERO_DOCUMENTO}: {sum(i.cantidad for i in items)} pzas, total ${compra.total}")

        if args.aplicar:
            session.commit()
            print("Listo: cambios guardados.")
        else:
            session.rollback()
            print("Simulacion: no se guardo nada. Agrega --aplicar para guardar.")


if __name__ == "__main__":
    main()
