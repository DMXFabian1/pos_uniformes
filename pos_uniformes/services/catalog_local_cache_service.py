"""Cache local del catalogo para modo offline del satelite.

Guarda el ultimo snapshot del catalogo en un archivo JSON junto al ejecutable.
Al arrancar sin conexion, el satelite puede leer este archivo y mostrar
el catalogo completo sin necesitar la PC principal.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from pos_uniformes.utils.config import runtime_base_dir

_CACHE_FILENAME = "catalog_cache.json"
_DATA_SUBDIR = "data"


def _cache_path() -> Path:
    return runtime_base_dir() / _DATA_SUBDIR / _CACHE_FILENAME


def save_catalog_cache(rows: list[dict]) -> None:
    """Persiste el snapshot del catalogo en disco.

    Sobreescribe cualquier cache anterior. Se llama despues de cada
    refresh exitoso del catalogo cuando hay conexion.
    """
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }
    path.write_text(
        json.dumps(payload, default=_json_default, ensure_ascii=False),
        encoding="utf-8",
    )


def load_catalog_cache() -> list[dict] | None:
    """Lee el ultimo snapshot guardado.

    Devuelve None si no existe o si el archivo esta corrupto.
    """
    path = _cache_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("rows")
        if not isinstance(rows, list):
            return None
        return rows
    except Exception:  # noqa: BLE001
        return None


def catalog_cache_saved_at() -> str | None:
    """Devuelve el timestamp ISO del ultimo guardado, o None si no hay cache."""
    path = _cache_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("saved_at")
    except Exception:  # noqa: BLE001
        return None


def format_cache_age_label(saved_at_iso: str) -> str:
    """Convierte el timestamp ISO a un texto legible para el banner de modo local.

    Ejemplo: 'guardado el 14/04/2026 a las 09:31'
    """
    try:
        dt = datetime.fromisoformat(saved_at_iso)
        local_dt = dt.astimezone()
        return local_dt.strftime("guardado el %d/%m/%Y a las %H:%M")
    except Exception:  # noqa: BLE001
        return "guardado anteriormente"


def _json_default(obj: object) -> object:
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Objeto no serializable: {type(obj)!r}")
