"""Aplicacion FastAPI principal para la API movil del POS."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pos_uniformes.api.routers import health, auth, catalog, clients, quotes, sales


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicacion."""
    # Aqui se puede agregar warmup de pool, precarga de cache, etc.
    yield


app = FastAPI(
    title="POS Uniformes — API Movil",
    version="1.0.0",
    description="API REST para la app movil de empleadas. Red local (LAN) exclusivamente.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — red local, se permiten todos los origenes.
# Restringir por IP si se requiere mayor control en el futuro.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(quotes.router)
app.include_router(sales.router)
