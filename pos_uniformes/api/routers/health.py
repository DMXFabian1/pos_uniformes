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

    return {
        "status": "ok" if db_ok else "degradado",
        "api_version": API_VERSION,
        "database": "conectada" if db_ok else "sin_conexion",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
