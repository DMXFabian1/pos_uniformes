"""Aplicacion FastAPI principal para la API movil del POS."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pos_uniformes.api.routers import health, auth, catalog, clients, favorites, precios, quotes, sales, search, whatsapp


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicacion."""
    _try_meilisearch_warmup()
    yield


def _try_meilisearch_warmup() -> None:
    try:
        from pos_uniformes.services import meilisearch_service
        from pos_uniformes.database.connection import get_session
        if not meilisearch_service.is_available():
            return
        meilisearch_service.configure_index()
        with get_session() as session:
            count = meilisearch_service.index_from_db(session)
            if count:
                import logging
                logging.getLogger(__name__).info("Meilisearch: %d variantes indexadas al iniciar.", count)
    except Exception:
        pass


app = FastAPI(
    title="POS Uniformes — API Movil",
    version="1.0.0",
    description="API REST para la app movil de empleadas. Red local (LAN) exclusivamente.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — red local. Configurable via POS_CORS_ORIGINS (comas).
_DEFAULT_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
_env_origins = os.environ.get("POS_CORS_ORIGINS", "")
_ALLOWED_ORIGINS = [o.strip() for o in _env_origins.split(",") if o.strip()] if _env_origins else _DEFAULT_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Manejador global de errores no capturados
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "error_interno",
                "message": "Error interno del servidor.",
                "detail": None,
            }
        },
    )


# Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(clients.router)
app.include_router(favorites.router)
app.include_router(quotes.router)
app.include_router(sales.router)
app.include_router(search.router)
app.include_router(whatsapp.router)
app.include_router(precios.router)
