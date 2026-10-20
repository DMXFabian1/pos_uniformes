"""La bandeja «Por nombrar»: ropa normal que entró con el código del proveedor.

La mercancía llega y se da de alta el mismo día con el código que trae
(«YT0572», «Sudadera KY357H») para que se pueda etiquetar y vender desde el
primer minuto; Daniel la va nombrando conforme la saca (2026-10-20). Esto
lista lo que falta y lo nombra desde el POS o desde el celular por el mismo
camino: nombre con código, pieza, detalle, color y género.

Convención del repo: mutan la Session pero NO hacen commit.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    AtributoProducto,
    Producto,
    TipoPieza,
    Usuario,
    Variante,
)


class NoSePuede(Exception):
    """Algo impide nombrarlo, dicho para enseñarlo en pantalla."""


@dataclass(frozen=True)
class Pendiente:
    producto_id: int
    nombre: str
    marca: str
    categoria: str
    pieza: str
    detalle: str
    genero: str
    color: str
    precio: str
    existencia: int
    skus: list[str]
    desde: str            # fecha de alta, dd/mm


def _sin_acentos(texto: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").casefold())
        if unicodedata.category(c) != "Mn"
    ).strip()


def listar(session: Session) -> list[Pendiente]:
    """Lo que falta nombrar, lo más viejo primero (lo que más urge)."""
    salida: list[Pendiente] = []
    productos = session.scalars(
        select(Producto)
        .where(Producto.por_identificar.is_(True), Producto.activo.is_(True))
        .order_by(Producto.created_at, Producto.id)
    ).all()
    for p in productos:
        variantes = [v for v in p.variantes if v.activo]
        colores = sorted({str(v.color or "") for v in variantes if v.color})
        precios = sorted({str(v.precio_venta) for v in variantes})
        salida.append(Pendiente(
            producto_id=p.id,
            nombre=p.nombre,
            marca=p.marca.nombre if p.marca else "",
            categoria=p.categoria.nombre if p.categoria else "",
            pieza=p.tipo_pieza.nombre if p.tipo_pieza else "",
            detalle=p.atributo.nombre if p.atributo else "",
            genero=p.genero or "",
            color=colores[0] if len(colores) == 1 else ", ".join(colores),
            precio=precios[0] if len(precios) == 1 else " / ".join(precios),
            existencia=sum(int(v.stock_actual or 0) for v in variantes),
            skus=[v.sku for v in variantes],
            desde=p.created_at.astimezone().strftime("%d/%m") if p.created_at else "",
        ))
    return salida


def cuantos(session: Session) -> int:
    return int(session.scalar(
        select(func.count()).select_from(Producto)
        .where(Producto.por_identificar.is_(True), Producto.activo.is_(True))
    ) or 0)


def _por_nombre(session: Session, modelo, nombre: str):
    """La fila con ese nombre, sin importar mayúsculas ni acentos, o una nueva.

    Prefiere la que lleva acento si hay dos («Basico»/«Básico»)."""
    import unicodedata

    nombre = " ".join((nombre or "").split())
    if not nombre:
        return None
    buscado = _sin_acentos(nombre)
    parecidas = [f for f in session.scalars(select(modelo)).all() if _sin_acentos(f.nombre) == buscado]
    if parecidas:
        def _acentuada(f) -> bool:
            return any(unicodedata.category(c) == "Mn" for c in unicodedata.normalize("NFD", f.nombre))

        parecidas.sort(key=lambda f: (not _acentuada(f), f.id))
        return parecidas[0]
    nueva = modelo(nombre=nombre)
    session.add(nueva)
    session.flush()
    return nueva


def nombrar(
    session: Session,
    usuario: Usuario,
    producto_id: int,
    *,
    nombre: str,
    pieza: str = "",
    detalle: str = "",
    color: str = "",
    genero: str = "",
    listo: bool = True,
) -> Producto:
    """Le pone nombre y ficha; con `listo` sale de la bandeja.

    Pasa por `CatalogService` (permiso de admin, historial de cambios y aviso
    a la búsqueda), no por SQL directo: es la regla desde la auditoría del
    alta de productos (2026-10-12)."""
    from pos_uniformes.services.catalog_service import CatalogService

    producto = session.get(Producto, int(producto_id))
    if producto is None:
        raise NoSePuede("Ese producto ya no existe.")
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise NoSePuede("Escribe el nombre.")
    if listo and not pieza.strip() and producto.tipo_pieza is None:
        raise NoSePuede("Di qué prenda es (la pieza) para darlo por nombrado.")

    tipo_pieza = _por_nombre(session, TipoPieza, pieza) if pieza.strip() else producto.tipo_pieza
    atributo = _por_nombre(session, AtributoProducto, detalle) if detalle.strip() else producto.atributo
    try:
        CatalogService.actualizar_producto(
            session,
            usuario,
            producto,
            categoria=producto.categoria,
            marca=producto.marca,
            nombre=nombre,
            descripcion=producto.descripcion,
            escuela=producto.escuela,
            tipo_prenda=producto.tipo_prenda,
            tipo_pieza=tipo_pieza,
            nivel_educativo=producto.nivel_educativo,
            atributo=atributo,
            genero=(genero.strip() or producto.genero),
            escudo=producto.escudo,
            ubicacion=producto.ubicacion,
        )
    except ValueError as exc:
        raise NoSePuede(str(exc)) from exc

    color = " ".join((color or "").split())
    if color:
        for v in producto.variantes:
            if v.activo and (v.color or "") != color:
                CatalogService.actualizar_variante(
                    session, usuario, v, producto,
                    sku=v.sku, talla=v.talla, color=color,
                    precio_venta=v.precio_venta, costo_referencia=v.costo_referencia,
                    stock_minimo=v.stock_minimo,
                )
    producto.por_identificar = not listo
    session.flush()
    return producto


def marcar(session: Session, producto: Producto, *, por_identificar: bool = True) -> None:
    producto.por_identificar = bool(por_identificar)
    session.flush()


def skus_de(session: Session, producto_ids: list[int]) -> list[int]:
    """Los ids de variante activos de esos productos (para imprimir etiquetas)."""
    if not producto_ids:
        return []
    return list(session.scalars(
        select(Variante.id).where(Variante.producto_id.in_(producto_ids), Variante.activo.is_(True))
        .order_by(Variante.producto_id, Variante.id)
    ).all())
