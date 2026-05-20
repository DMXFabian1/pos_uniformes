"""Endpoint de búsqueda rápida con Meilisearch."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.schemas.catalog import ProductFamilyOut
from pos_uniformes.services import meilisearch_service

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("")
def search_products(
    q: str = Query(..., min_length=1, description="Texto de búsqueda"),
    mode: str | None = Query(default=None, description="Filtrar por modo: school o basics"),
    limit: int = Query(default=40, ge=1, le=100),
    _auth=Depends(get_current_employee),
):
    if not meilisearch_service.is_available():
        return {"families": [], "available": False}

    families = meilisearch_service.search_as_families(q, limit=limit, mode=mode)
    return {"families": families, "available": True}


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
