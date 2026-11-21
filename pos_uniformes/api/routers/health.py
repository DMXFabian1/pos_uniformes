"""Endpoint de salud de la API."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from pos_uniformes.api.dependencies import get_db

router = APIRouter(tags=["health"])

API_VERSION = "1.0.0"


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    """
    Verifica que la API y la base de datos estan operativas.
    Consumido por el satelite desktop, la PWA y el monitoreo de NSSM.
    """
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    respuesta = {
        "status": "ok" if db_ok else "degradado",
        "api_version": API_VERSION,
        "database": "conectada" if db_ok else "sin_conexion",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    # Copia de casa: ¿este código va en la misma versión de base que la tienda?
    # (la vigila el latido de nucleo). En la tienda, /health igual que siempre.
    from pos_uniformes.utils.config import modo_pwa

    if db_ok and modo_pwa() == "casa":
        from pos_uniformes.services.version_base_service import estado_version

        respuesta["version_base"] = estado_version(db)
    return respuesta
