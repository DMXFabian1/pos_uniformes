"""Endpoints de favoritos para la PWA.

Delega en satellite_favorites_service para compartir el mismo favorites.json
que usa el satélite de escritorio (satellite_data_dir/data/favorites.json).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pos_uniformes.api.dependencies import get_current_employee
from pos_uniformes.services.satellite_favorites_service import load_favorites, toggle_favorite

router = APIRouter(prefix="/api/v1/favorites", tags=["favorites"])


class FavoritesOut(BaseModel):
    product_keys: list[str]


class ToggleIn(BaseModel):
    product_key: str


class ToggleOut(BaseModel):
    product_key: str
    active: bool


@router.get("", response_model=FavoritesOut)
def get_favorites(
    _auth=Depends(get_current_employee),
) -> FavoritesOut:
    """Devuelve el conjunto de product_keys marcados como favoritos."""
    return FavoritesOut(product_keys=sorted(load_favorites()))


@router.post("/toggle", response_model=ToggleOut)
def toggle_favorite_key(
    body: ToggleIn,
    _auth=Depends(get_current_employee),
) -> ToggleOut:
    """Alterna el favorito para product_key. Retorna si quedó activo o no."""
    active = toggle_favorite(body.product_key)
    return ToggleOut(product_key=body.product_key, active=active)
