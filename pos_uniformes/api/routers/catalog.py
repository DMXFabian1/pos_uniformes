"""Endpoints de catalogo de productos para la API movil."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.schemas.catalog import CatalogPage, ProductoListItem, ProductoOut, VarianteOut
from pos_uniformes.database.models import Categoria, Marca, Producto, Variante

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])

DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100


@router.get("", response_model=CatalogPage)
def list_products(
    q: str | None = Query(default=None, description="Busqueda por nombre, SKU o categoria"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    _auth=Depends(get_current_employee),
) -> CatalogPage:
    """
    Lista paginada de productos activos con al menos una variante activa.
    Soporta busqueda libre por nombre, SKU o categoria.
    """
    stmt = (
        select(Producto)
        .join(Producto.variantes)
        .join(Producto.categoria)
        .join(Producto.marca)
        .where(Producto.activo.is_(True), Variante.activo.is_(True))
        .options(
            selectinload(Producto.variantes),
            selectinload(Producto.categoria),
            selectinload(Producto.marca),
        )
        .distinct()
    )

    if q:
        term = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Producto.nombre).like(term),
                func.lower(Categoria.nombre).like(term),
                func.lower(Variante.sku).like(term),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = stmt.order_by(Producto.nombre.asc()).offset((page - 1) * page_size).limit(page_size)
    productos = db.scalars(stmt).all()

    items = []
    for p in productos:
        variantes_activas = [v for v in p.variantes if v.activo]
        if not variantes_activas:
            continue
        precio_desde = min((v.precio_venta for v in variantes_activas), default=Decimal("0"))
        items.append(
            ProductoListItem(
                id=p.id,
                nombre=p.nombre,
                categoria=p.categoria.nombre,
                marca=p.marca.nombre,
                precio_desde=precio_desde,
                total_variantes=len(variantes_activas),
            )
        )

    return CatalogPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{producto_id}", response_model=ProductoOut)
def get_product(
    producto_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(get_current_employee),
) -> ProductoOut:
    """Detalle completo de un producto con todas sus variantes activas."""
    producto = db.scalar(
        select(Producto)
        .where(Producto.id == producto_id, Producto.activo.is_(True))
        .options(
            selectinload(Producto.variantes),
            selectinload(Producto.categoria),
            selectinload(Producto.marca),
        )
    )
    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "producto_no_encontrado", "message": "Producto no encontrado."}},
        )

    variantes_activas = [v for v in producto.variantes if v.activo]
    return ProductoOut(
        id=producto.id,
        nombre=producto.nombre,
        categoria=producto.categoria.nombre,
        marca=producto.marca.nombre,
        descripcion=producto.descripcion,
        activo=producto.activo,
        variantes=[
            VarianteOut(
                id=v.id,
                sku=v.sku,
                talla=v.talla,
                color=v.color,
                precio_venta=v.precio_venta,
                stock_actual=v.stock_actual,
            )
            for v in variantes_activas
        ],
    )


@router.get("/sku/{sku}", response_model=VarianteOut)
def get_by_sku(
    sku: str,
    db: Session = Depends(get_db),
    _auth=Depends(get_current_employee),
) -> VarianteOut:
    """
    Consulta rapida de precio por SKU o codigo de barras escaneado.
    Endpoint principal del scanner de producto en la PWA.
    """
    variante = db.scalar(
        select(Variante).where(
            func.upper(Variante.sku) == sku.strip().upper(),
            Variante.activo.is_(True),
        )
    )
    if variante is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "sku_no_encontrado", "message": f"No se encontro producto con SKU '{sku}'."}},
        )
    return VarianteOut(
        id=variante.id,
        sku=variante.sku,
        talla=variante.talla,
        color=variante.color,
        precio_venta=variante.precio_venta,
        stock_actual=variante.stock_actual,
    )
