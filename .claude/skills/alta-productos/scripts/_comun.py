"""Piezas compartidas por los scripts de la skill alta-productos.

- Pone la raíz del repo en sys.path para importar `pos_uniformes`.
- Silencia avisos que solo gastan tokens (deprecaciones de SQLAlchemy).
- `--env-file`: carga un pos_uniformes.env (p. ej. el que apunta a la caja)
  ANTES de importar la configuración del proyecto.
- `motor(args)`: engine con --db-url, o con la configuración ya cargada.
"""
from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*noload.*")

LOCALES = {"localhost", "127.0.0.1", "::1", None, ""}


def agregar_argumentos_db(ap) -> None:
    ap.add_argument("--db-url", help="URL SQLAlchemy completa (gana sobre todo lo demás)")
    ap.add_argument(
        "--env-file",
        help="pos_uniformes.env a cargar (p. ej. el de la caja); sin esto se usa la config del proyecto",
    )


def cargar_env(ruta: str | None) -> None:
    if not ruta:
        return
    archivo = Path(ruta).expanduser()
    if not archivo.is_file():
        raise SystemExit(f"ERROR: no existe el env «{archivo}».")
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ[clave.strip()] = valor.strip().strip('"').strip("'")


def motor(args, *, solo_lectura: bool = False):
    """Engine según --db-url / --env-file / config del proyecto. Imprime el destino."""
    cargar_env(getattr(args, "env_file", None))
    from sqlalchemy import create_engine

    url = getattr(args, "db_url", None)
    if not url:
        from pos_uniformes.utils.config import Settings

        url = Settings.from_env().database_url
    connect_args = {"connect_timeout": 5}
    if solo_lectura:
        connect_args["options"] = "-c default_transaction_read_only=on"
    engine = create_engine(url, connect_args=connect_args)
    host = engine.url.host
    aviso = "" if host in LOCALES else "  ⚠ PRODUCCIÓN / RED"
    print(f"DB: {host or 'local'}/{engine.url.database}{' (solo lectura)' if solo_lectura else ''}{aviso}")
    return engine
