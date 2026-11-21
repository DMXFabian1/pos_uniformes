"""Aplicacion FastAPI principal para la API movil del POS."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pos_uniformes.api.routers import health, auth, bodega_movil, catalog, clients, conteos_movil, favorites, movil, quotes, sales, search


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicacion."""
    _try_meilisearch_warmup()
    yield


def _try_meilisearch_warmup() -> None:
    from pos_uniformes.api.routers.movil import _modo_servidor

    if _modo_servidor() == "casa":
        return  # la casa solo consulta: no reindexa nada
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

# Modo casa (POS_PWA_MODO=casa): la copia de la casa SOLO consulta. Todo lo
# que no sea leer se rechaza aquí, antes de llegar a cualquier router, con el
# mismo 409 «solo_en_tienda» que la PWA ya sabe mostrar. Entrar y salir sí
# (no escriben nada: el JWT no se guarda en la base), y pedir una copia nueva
# de la tienda (/movil/actualizar: se la pide al servidor de casa, no toca la base).
_METODOS_DE_LECTURA = {"GET", "HEAD", "OPTIONS"}
_PERMITIDOS_EN_CASA = {"/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/movil/actualizar"}


@app.middleware("http")
async def solo_lectura_en_casa(request: Request, call_next):
    if request.method not in _METODOS_DE_LECTURA:
        from pos_uniformes.api.routers.movil import SOLO_EN_TIENDA, _modo_servidor

        ruta = request.url.path.rstrip("/") or "/"
        if _modo_servidor() == "casa" and ruta not in _PERMITIDOS_EN_CASA:
            return JSONResponse(status_code=409, content={"detail": SOLO_EN_TIENDA})
    return await call_next(request)


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
app.include_router(movil.router)
app.include_router(conteos_movil.router)
app.include_router(bodega_movil.router)
app.include_router(quotes.router)
app.include_router(sales.router)
app.include_router(search.router)

# PWA (Libreta móvil): estáticos en /app, y la raíz redirige ahí.
from pathlib import Path as _Path

from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

_PWA_DIR = _Path(__file__).resolve().parents[1] / "pwa"
if _PWA_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(_PWA_DIR), html=True), name="pwa")

    @app.get("/", include_in_schema=False)
    def _raiz() -> RedirectResponse:
        return RedirectResponse("/app/")
