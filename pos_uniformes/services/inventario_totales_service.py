"""Los totales del inventario, en un solo lugar.

Hasta ahora estas cuentas vivían escritas a mano en el SQL del generador del
panel de uniformes: qué es "lo que hay en tienda", qué producto "es de una
escuela", desde cuándo una talla está "bajo mínimo" y qué no se suma porque ya
viene contado en otra pieza. Cada definición repetida es un desfase esperando
su turno, así que aquí quedan una sola vez y quien las necesite las pide.

Ver la nota `39 - Brújula` del vault: ninguna ventana calcula, todas preguntan.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    BodegaCaja,
    BodegaContenido,
    BodegaUbicacion,
    CatalogSchoolProductLink,
    NivelEducativo,
    Producto,
    Variante,
)
from pos_uniformes.services import conjunto_service

#: Cuando una talla no dice su mínimo, se asume este.
STOCK_MINIMO_DEFAULT = 2

#: El rack que significa "está en el piso, a la mano", no guardado en caja.
RACK_PISO = "PISO"


@dataclass(frozen=True)
class TotalesInventario:
    """Las cifras del encabezado del panel. Todas excluyen los conjuntos."""

    stock_total: int
    stock_bodega: int
    stock_piso: int
    stock_tienda: int
    variantes_sin_stock: int
    variantes_bajo_minimo: int
    valor_inventario: float
    variantes_con_escuela: int


# --------------------------------------------------------------- definiciones

def subconsulta_bodega():
    """Lo que cada talla tiene guardado, partido en piso y bodega.

    El piso es lo que está a la mano; la bodega, lo que está en cajas. Sale de
    `bodega_contenido`, no de una columna: por eso hace falta agrupar."""
    piso = func.coalesce(
        func.sum(
            case(
                (func.upper(BodegaUbicacion.rack) == RACK_PISO, BodegaContenido.cantidad),
                else_=0,
            )
        ),
        0,
    )
    bodega = func.coalesce(
        func.sum(
            case(
                (func.upper(BodegaUbicacion.rack) != RACK_PISO, BodegaContenido.cantidad),
                else_=0,
            )
        ),
        0,
    )
    return (
        select(
            BodegaContenido.variante_id.label("variante_id"),
            piso.label("piso"),
            bodega.label("bodega"),
        )
        .join(BodegaCaja, BodegaCaja.id == BodegaContenido.caja_id)
        .join(BodegaUbicacion, BodegaUbicacion.id == BodegaCaja.ubicacion_id)
        .group_by(BodegaContenido.variante_id)
        .subquery()
    )


def expr_stock_tienda(bodega_sq):
    """Lo que de verdad está en el mostrador: el total menos lo guardado.

    Misma cuenta que `Variante.stock_tienda`, pero en SQL, para poder sumarla
    sobre miles de tallas sin traerlas una por una."""
    return (
        Variante.stock_actual
        - func.coalesce(bodega_sq.c.bodega, 0)
        - func.coalesce(bodega_sq.c.piso, 0)
    )


def filtro_producto_de_escuela():
    """Un producto es "de escuela" si lo es de nacimiento o si alguien lo ligó.

    Los básicos (un pants liso, un suéter vino) no nacen con escuela: se ligan
    desde el catálogo guiado. Para las cuentas de cobertura cuentan igual."""
    return or_(
        Producto.escuela_id.is_not(None),
        Producto.id.in_(
            select(CatalogSchoolProductLink.producto_id).where(
                CatalogSchoolProductLink.activo.is_(True)
            )
        ),
    )


def expr_bajo_minimo(stock_tienda):
    """Le queda algo, pero menos de lo que esa talla debería tener."""
    minimo = func.coalesce(Variante.stock_minimo, STOCK_MINIMO_DEFAULT)
    return (stock_tienda > 0) & (stock_tienda < minimo)


# ------------------------------------------------------------------- consultas

def totales_inventario(session: Session) -> TotalesInventario:
    """Las ocho cifras del encabezado, en un solo viaje a la base."""
    bodega_sq = subconsulta_bodega()
    tienda = expr_stock_tienda(bodega_sq)
    de_escuela = filtro_producto_de_escuela()

    def cuantas(condicion):
        return func.coalesce(func.sum(case((condicion, 1), else_=0)), 0)

    fila = session.execute(
        select(
            func.coalesce(func.sum(Variante.stock_actual), 0),
            func.coalesce(func.sum(func.coalesce(bodega_sq.c.bodega, 0)), 0),
            func.coalesce(func.sum(func.coalesce(bodega_sq.c.piso, 0)), 0),
            func.coalesce(func.sum(tienda), 0),
            cuantas(de_escuela & (tienda <= 0)),
            cuantas(de_escuela & expr_bajo_minimo(tienda)),
            func.coalesce(func.sum(Variante.stock_actual * Variante.precio_venta), 0),
            cuantas(de_escuela),
        )
        .select_from(Variante)
        .join(Producto, Producto.id == Variante.producto_id)
        .outerjoin(bodega_sq, bodega_sq.c.variante_id == Variante.id)
        .where(
            Variante.activo.is_(True),
            Producto.activo.is_(True),
            conjunto_service.filtro_sin_conjuntos(),
        )
    ).one()

    return TotalesInventario(
        stock_total=int(fila[0]),
        stock_bodega=int(fila[1]),
        stock_piso=int(fila[2]),
        stock_tienda=int(fila[3]),
        variantes_sin_stock=int(fila[4]),
        variantes_bajo_minimo=int(fila[5]),
        valor_inventario=float(fila[6]),
        variantes_con_escuela=int(fila[7]),
    )


def valor_por_nivel(session: Session) -> dict[str, float]:
    """Cuánto dinero hay parado en cada nivel educativo.

    Aquí sí cuenta solo la escuela de nacimiento del producto (no las ligas):
    un básico general no pertenece al nivel de nadie en particular."""
    filas = session.execute(
        select(
            NivelEducativo.nombre,
            func.coalesce(func.sum(Variante.stock_actual * Variante.precio_venta), 0),
        )
        .select_from(Variante)
        .join(Producto, Producto.id == Variante.producto_id)
        .join(NivelEducativo, NivelEducativo.id == Producto.nivel_educativo_id)
        .where(
            Variante.activo.is_(True),
            Producto.activo.is_(True),
            Producto.escuela_id.is_not(None),
            conjunto_service.filtro_sin_conjuntos(),
        )
        .group_by(NivelEducativo.nombre)
        .order_by(NivelEducativo.nombre)
    ).all()
    return {nombre: float(valor) for nombre, valor in filas}
