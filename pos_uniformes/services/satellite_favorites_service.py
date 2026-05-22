"""Favoritos locales del satélite — piezas que se presupuestan con más frecuencia.

Se persisten en satellite_data_dir/data/favorites.json junto al cache del catálogo.
Funcionan online y offline. Cada satélite puede tener sus propios favoritos.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

from pos_uniformes.utils.config import satellite_data_dir

_FAVORITES_FILENAME = "favorites.json"
_DATA_SUBDIR = "data"


def _favorites_path() -> Path:
    return satellite_data_dir() / _DATA_SUBDIR / _FAVORITES_FILENAME


def load_favorites() -> set[str]:
    """Devuelve el conjunto de product_keys marcados como favoritos."""
    path = _favorites_path()
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        keys = data.get("product_keys")
        if isinstance(keys, list):
            return {str(k) for k in keys}
    except Exception:  # noqa: BLE001
        logger.warning("No se pudo leer favorites.json", exc_info=True)
    return set()


def save_favorites(product_keys: set[str]) -> None:
    """Persiste el conjunto de product_keys favoritos."""
    path = _favorites_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps({"product_keys": sorted(product_keys)}, ensure_ascii=False)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def seed_favorites_from_bundle() -> None:
    """En el bundle de Windows: copia favorites.json del bundle al AppData si no existe.

    Permite que los favoritos marcados en el Mac de desarrollo lleguen al build de Windows
    sin sobreescribir favoritos que las empleadas ya hayan guardado.
    Solo corre cuando la app está frozen (PyInstaller).
    """
    if not getattr(sys, "frozen", False):
        return
    dest = _favorites_path()
    if dest.exists():
        return
    bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    seed = bundle_dir / _DATA_SUBDIR / _FAVORITES_FILENAME
    if not seed.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed, dest)


def toggle_favorite(product_key: str) -> bool:
    """Alterna el favorito para product_key. Retorna True si quedó marcado."""
    keys = load_favorites()
    if product_key in keys:
        keys.discard(product_key)
    else:
        keys.add(product_key)
    save_favorites(keys)
    return product_key in keys
