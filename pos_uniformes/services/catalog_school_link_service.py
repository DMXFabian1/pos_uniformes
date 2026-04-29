"""CRUD de ligas manuales entre productos generales y escuelas."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from pos_uniformes.database.models import CatalogSchoolProductLink, Escuela, Producto


def list_all_active_links(session) -> list[dict]:
    links = session.scalars(
        select(CatalogSchoolProductLink)
        .options(
            joinedload(CatalogSchoolProductLink.escuela),
            joinedload(CatalogSchoolProductLink.producto),
        )
        .where(CatalogSchoolProductLink.activo == True)  # noqa: E712
        .order_by(CatalogSchoolProductLink.escuela_id, CatalogSchoolProductLink.id)
    ).all()
    return [
        {
            "link_id": int(link.id),
            "escuela_id": int(link.escuela_id),
            "escuela_nombre": str(link.escuela.nombre),
            "producto_id": int(link.producto_id),
            "producto_nombre_base": str(link.producto.nombre_base or link.producto.nombre),
        }
        for link in links
    ]


def list_links_by_school(session, escuela_id: int) -> list[dict]:
    links = session.scalars(
        select(CatalogSchoolProductLink)
        .options(joinedload(CatalogSchoolProductLink.producto))
        .where(
            CatalogSchoolProductLink.escuela_id == int(escuela_id),
            CatalogSchoolProductLink.activo == True,  # noqa: E712
        )
        .order_by(CatalogSchoolProductLink.id)
    ).all()
    return [
        {
            "link_id": int(link.id),
            "producto_id": int(link.producto_id),
            "producto_nombre_base": str(link.producto.nombre_base or link.producto.nombre),
        }
        for link in links
    ]


def list_all_schools(session) -> list[dict]:
    schools = session.scalars(
        select(Escuela).where(Escuela.activo == True).order_by(Escuela.nombre)  # noqa: E712
    ).all()
    return [{"escuela_id": int(s.id), "escuela_nombre": str(s.nombre)} for s in schools]


def list_general_products(session) -> list[dict]:
    """Devuelve productos sin escuela asignada (los 'generales' del catálogo)."""
    products = session.scalars(
        select(Producto)
        .where(Producto.escuela_id == None, Producto.activo == True)  # noqa: E711, E712
        .order_by(Producto.nombre_base, Producto.nombre)
    ).all()
    seen: set[str] = set()
    unique: list[dict] = []
    for p in products:
        nombre_base = str(p.nombre_base or p.nombre).strip()
        if nombre_base in seen:
            continue
        seen.add(nombre_base)
        unique.append({"producto_id": int(p.id), "producto_nombre_base": nombre_base})
    return unique


def add_school_product_link(session, *, escuela_id: int, producto_id: int) -> dict:
    existing = session.scalar(
        select(CatalogSchoolProductLink).where(
            CatalogSchoolProductLink.escuela_id == int(escuela_id),
            CatalogSchoolProductLink.producto_id == int(producto_id),
        )
    )
    if existing is not None:
        if not existing.activo:
            existing.activo = True
            session.flush()
        return {
            "link_id": int(existing.id),
            "producto_id": int(existing.producto_id),
        }
    link = CatalogSchoolProductLink(escuela_id=int(escuela_id), producto_id=int(producto_id))
    session.add(link)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise ValueError("Ya existe una liga para esa combinación de escuela y producto.")
    return {"link_id": int(link.id), "producto_id": int(link.producto_id)}


def remove_school_product_link(session, *, link_id: int) -> None:
    link = session.get(CatalogSchoolProductLink, int(link_id))
    if link is not None:
        session.delete(link)
        session.flush()
