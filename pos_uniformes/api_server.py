"""Punto de entrada para el servidor API movil del POS.

Uso:
    python api_server.py

Para produccion en Windows (via NSSM):
    uvicorn pos_uniformes.api.main:app --host 0.0.0.0 --port 8000 --workers 1

Variables de entorno relevantes (en pos_uniformes.env):
    POS_API_SECRET_KEY      Clave secreta para firmar JWT. Cambiar en produccion.
    POS_API_HOST            Host donde escucha la API. Default: 0.0.0.0
    POS_API_PORT            Puerto. Default: 8000
    POS_API_TOKEN_EXPIRE_HOURS  Duracion del token en horas. Default: 8
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pos_uniformes.utils.venv_bootstrap import ensure_local_venv_site_packages

ensure_local_venv_site_packages(Path(__file__))

import uvicorn

from pos_uniformes.utils.config import settings


def main() -> None:
    uvicorn.run(
        "pos_uniformes.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=1,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
