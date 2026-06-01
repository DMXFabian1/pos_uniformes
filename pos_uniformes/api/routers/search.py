"""Endpoint de busqueda rapida — Meilisearch con fallback a Postgres."""

from __future__ import annotations

import unicodedata

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.routers.catalog import _pieza_sort_key, _talla_sort_key
from pos_uniformes.api.schemas.catalog import ProductFamilyOut
from pos_uniformes.database.models import Producto, TipoPieza, Variante
from pos_uniformes.services import meilisearch_service

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("")
def search_products(
    q: str = Query(..., min_length=1, description="Texto de busqueda"),
    mode: str | None = Query(default=None, description="Filtrar por modo: school o basics"),
    limit: int = Query(default=40, ge=1, le=100),
    db: Session = Depends(get_db),
    _auth=Depends(get_current_employee),
):
    if meilisearch_service.is_available():
        families = meilisearch_service.search_as_families(q, limit=limit, mode=mode)
        return {"families": families, "available": True}

    return _sql_fallback_search(db, q, mode, limit)


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _sql_fallback_search(db: Session, q: str, mode: str | None, limit: int):
    """Busqueda full-text en Postgres cuando Meilisearch no esta disponible."""
    q_clean = _strip_accents(q.lower())
    pattern = f"%{q_clean}%"

    stmt = (
        select(Producto)
        .join(Producto.variantes)
        .where(
            Producto.activo.is_(True),
            Variante.activo.is_(True),
            or_(
                func.unaccent(func.lower(Producto.nombre_base)).ilike(pattern),
                func.unaccent(func.lower(Producto.nombre)).ilike(pattern),
                func.lower(Variante.sku).ilike(f"%{q.lower()}%"),
                Producto.tipo_pieza.has(
                    func.unaccent(func.lower(TipoPieza.nombre)).ilike(pattern)
                ),
            ),
        )
        .options(
            selectinload(Producto.variantes),
            selectinload(Producto.tipo_pieza),
        )
        .distinct()
    )

    if mode == "school":
        stmt = stmt.where(Producto.escuela_id.isnot(None))
    elif mode == "basics":
        stmt = stmt.where(Producto.escuela_id.is_(None))

    productos = db.scalars(stmt).all()

    families_map: dict[str, dict] = {}
    for p in productos:
        variantes_activas = [v for v in p.variantes if v.activo]
        if not variantes_activas:
            continue

        tipo_pieza_nombre = p.tipo_pieza.nombre if p.tipo_pieza else "Sin pieza"
        fam_key = f"{tipo_pieza_nombre}||{p.nombre_base}"

        if fam_key not in families_map:
            families_map[fam_key] = {
                "key": fam_key,
                "nombre_base": p.nombre_base,
                "tipo_pieza": tipo_pieza_nombre,
                "tipo_pieza_id": p.tipo_pieza_id,
                "precio_desde": min(v.precio_venta for v in variantes_activas),
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

    families = sorted(
        families_map.values(),
        key=lambda f: (_pieza_sort_key(f["tipo_pieza"]), f["nombre_base"]),
    )[:limit]

    for fam in families:
        fam["variantes"].sort(key=lambda v: (_talla_sort_key(v["talla"]), v["color"]))

    return {"families": families, "available": False, "fallback": "sql"}


@router.post("/reindex")
def reindex(
    db=Depends(get_db),
    _auth=Depends(get_current_employee),
):
    ok = meilisearch_service.configure_index()
    if not ok:
        return {"status": "error", "message": "Meilisearch no disponible", "indexed": 0}
    count = meilisearch_service.index_from_db(db)
    return {"status": "ok", "indexed": count}


@router.get("/status")
def search_status(
    _auth=Depends(get_current_employee),
):
    return {"available": meilisearch_service.is_available()}
