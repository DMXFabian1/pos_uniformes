"""Endpoints de catalogo de productos para la API movil."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.schemas.catalog import (
    CatalogPage,
    GuidedOptionsOut,
    GuidedProductsOut,
    ProductFamilyOut,
    ProductoListItem,
    ProductoOut,
    VarianteOut,
    VarianteScanOut,
)
from pos_uniformes.database.models import (
    Categoria,
    Escuela,
    Marca,
    NivelEducativo,
    Producto,
    TipoPieza,
    TipoPrenda,
    Variante,
)

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])

# ── Orden de tallas ───────────────────────────────────────────────────────────
_TALLA_ALPHA: dict[str, int] = {
    "XCH": 0, "XXS": 0,
    "CH": 1, "XS": 1,
    "M": 2, "S": 2,
    "G": 3,
    "XG": 4, "L": 4,
    "XXG": 5, "XL": 5,
    "XXXG": 6, "XXL": 6,
    "4XL": 7,
    "UNICA": 99,
}


def _talla_sort_key(talla: str) -> tuple:
    t = talla.strip().upper()
    if t in _TALLA_ALPHA:
        return (0, _TALLA_ALPHA[t], "")
    try:
        return (1, float(t), "")   # tallas numéricas (2, 4, 6, 8 …)
    except ValueError:
        return (2, 0, t)           # fallback alfabético

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


@router.get("/sku/{sku}", response_model=VarianteScanOut)
def get_by_sku(
    sku: str,
    db: Session = Depends(get_db),
    _auth=Depends(get_current_employee),
) -> VarianteScanOut:
    """
    Consulta rapida de precio por SKU o codigo de barras escaneado.
    Endpoint principal del scanner de producto en la PWA.
    Devuelve variante + datos del producto padre (nombre, categoria, marca).
    """
    variante = db.scalar(
        select(Variante)
        .where(
            func.upper(Variante.sku) == sku.strip().upper(),
            Variante.activo.is_(True),
        )
        .options(
            selectinload(Variante.producto).selectinload(Producto.categoria),
            selectinload(Variante.producto).selectinload(Producto.marca),
        )
    )
    if variante is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "sku_no_encontrado", "message": f"No se encontro producto con SKU '{sku}'."}},
        )
    p = variante.producto
    return VarianteScanOut(
        id=variante.id,
        sku=variante.sku,
        talla=variante.talla,
        color=variante.color,
        precio_venta=variante.precio_venta,
        stock_actual=variante.stock_actual,
        nombre=p.nombre,
        categoria=p.categoria.nombre,
        marca=p.marca.nombre,
        descripcion=p.descripcion,
    )


# ── Catálogo guiado ───────────────────────────────────────────────────────────

@router.get("/guided/options", response_model=GuidedOptionsOut)
def guided_options(
    db: Session = Depends(get_db),
    _auth=Depends(get_current_employee),
) -> GuidedOptionsOut:
    """
    Árbol de filtros para el catálogo guiado:
    - Niveles educativos con sus escuelas (solo las que tienen productos activos)
    - Tipos de pieza disponibles por modo (school / basics)
    """
    # Niveles con productos escolares activos
    nivel_rows = db.execute(
        select(NivelEducativo.id, NivelEducativo.nombre)
        .join(Producto, Producto.nivel_educativo_id == NivelEducativo.id)
        .join(Variante, Variante.producto_id == Producto.id)
        .where(
            NivelEducativo.activo.is_(True),
            Producto.activo.is_(True),
            Variante.activo.is_(True),
            Producto.escuela_id.isnot(None),
        )
        .distinct()
        .order_by(NivelEducativo.nombre)
    ).all()

    niveles = []
    for nivel_id, nivel_nombre in nivel_rows:
        escuela_rows = db.execute(
            select(Escuela.id, Escuela.nombre)
            .join(Producto, Producto.escuela_id == Escuela.id)
            .join(Variante, Variante.producto_id == Producto.id)
            .where(
                Escuela.activo.is_(True),
                Producto.activo.is_(True),
                Variante.activo.is_(True),
                Producto.nivel_educativo_id == nivel_id,
            )
            .distinct()
            .order_by(Escuela.nombre)
        ).all()
        niveles.append({
            "id": nivel_id,
            "nombre": nivel_nombre,
            "escuelas": [{"id": eid, "nombre": enombre} for eid, enombre in escuela_rows],
        })

    def _tipo_pieza_para_modo(school: bool) -> list[dict]:
        q = (
            select(TipoPieza.id, TipoPieza.nombre)
            .join(Producto, Producto.tipo_pieza_id == TipoPieza.id)
            .join(Variante, Variante.producto_id == Producto.id)
            .where(
                TipoPieza.activo.is_(True),
                Producto.activo.is_(True),
                Variante.activo.is_(True),
            )
        )
        if school:
            q = q.where(Producto.escuela_id.isnot(None))
        else:
            q = q.where(Producto.escuela_id.is_(None))
        rows = db.execute(q.distinct().order_by(TipoPieza.nombre)).all()
        return [{"id": r[0], "nombre": r[1]} for r in rows]

    return GuidedOptionsOut(
        niveles=niveles,
        tipo_pieza_school=_tipo_pieza_para_modo(True),
        tipo_pieza_basics=_tipo_pieza_para_modo(False),
    )


@router.get("/guided/products", response_model=GuidedProductsOut)
def guided_products(
    mode: str = Query(..., pattern="^(school|basics)$"),
    escuela_id: int | None = Query(default=None),
    tipo_prenda: str | None = Query(default=None),
    genero: str | None = Query(default=None),
    tipo_pieza_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _auth=Depends(get_current_employee),
) -> GuidedProductsOut:
    """
    Productos filtrados, agrupados por familia (nombre_base + tipo_pieza).
    También devuelve las opciones de filtro disponibles para la selección actual.
    - mode=school: productos con escuela asignada
    - mode=basics: productos sin escuela (básicos genéricos)
    """
    stmt = (
        select(Producto)
        .join(Producto.variantes)
        .where(Producto.activo.is_(True), Variante.activo.is_(True))
        .options(
            selectinload(Producto.variantes),
            selectinload(Producto.tipo_pieza),
            selectinload(Producto.tipo_prenda),
        )
        .distinct()
    )

    if mode == "school":
        stmt = stmt.where(Producto.escuela_id.isnot(None))
        if escuela_id is not None:
            stmt = stmt.where(Producto.escuela_id == escuela_id)
        if tipo_prenda:
            # Subquery para evitar conflicto de joins
            tp_ids = select(TipoPrenda.id).where(
                func.upper(TipoPrenda.nombre) == tipo_prenda.strip().upper()
            ).scalar_subquery()
            stmt = stmt.where(Producto.tipo_prenda_id == tp_ids)
        if genero:
            stmt = stmt.where(func.upper(Producto.genero) == genero.strip().upper())
    else:
        stmt = stmt.where(Producto.escuela_id.is_(None))

    if tipo_pieza_id is not None:
        stmt = stmt.where(Producto.tipo_pieza_id == tipo_pieza_id)

    productos = db.scalars(stmt).all()

    # Recopilar opciones de filtro disponibles en la selección actual
    genero_set: set[str] = set()
    tipo_prenda_set: set[str] = set()
    tipo_pieza_map: dict[int, str] = {}
    families_map: dict[str, dict] = {}

    for p in productos:
        if p.genero:
            genero_set.add(p.genero.strip().upper())
        if p.tipo_prenda:
            tipo_prenda_set.add(p.tipo_prenda.nombre.strip().upper())
        if p.tipo_pieza:
            tipo_pieza_map[p.tipo_pieza.id] = p.tipo_pieza.nombre

        variantes_activas = [v for v in p.variantes if v.activo]
        if not variantes_activas:
            continue

        fam_key = f"{p.nombre_base}||{p.tipo_pieza_id or 0}"
        if fam_key not in families_map:
            precio_desde = min(v.precio_venta for v in variantes_activas)
            families_map[fam_key] = {
                "key": fam_key,
                "nombre_base": p.nombre_base,
                "tipo_pieza": p.tipo_pieza.nombre if p.tipo_pieza else None,
                "tipo_pieza_id": p.tipo_pieza_id,
                "precio_desde": precio_desde,
                "variantes": [],
            }

        for v in variantes_activas:
            families_map[fam_key]["variantes"].append({
                "id": v.id,
                "sku": v.sku,
                "talla": v.talla,
                "color": v.color,
                "precio_venta": v.precio_venta,
                "stock_actual": v.stock_actual,
            })

    # Ordenar familias y variantes
    families = sorted(families_map.values(), key=lambda f: f["nombre_base"])
    for fam in families:
        fam["variantes"].sort(key=lambda v: (_talla_sort_key(v["talla"]), v["color"]))

    return GuidedProductsOut(
        genero_options=sorted(genero_set),
        tipo_prenda_options=sorted(tipo_prenda_set),
        tipo_pieza_options=sorted(
            [{"id": k, "nombre": v} for k, v in tipo_pieza_map.items()],
            key=lambda x: x["nombre"],
        ),
        families=[ProductFamilyOut(**f) for f in families],
    )
