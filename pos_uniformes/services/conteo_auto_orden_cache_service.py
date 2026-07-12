"""Candado local anti-spam para la impresión automática de órdenes de conteo.

Guarda, por escuela, el "marcador" (la próxima fecha de conteo) para el que ya
se generó la orden automática. Mientras el marcador no cambie, no se vuelve a
imprimir — así una escuela vencida no reimprime todos los días.

Cuando se registra un conteo, la próxima fecha se recorre → el marcador cambia →
la siguiente vez que venza se vuelve a generar. Es un cache POR MÁQUINA (vive en
satellite_data_dir), igual que los otros caches del satélite.
"""

from __future__ import annotations

import json
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_CACHE_FILENAME = "conteo_auto_orden.json"


def _cache_path() -> Path:
    return satellite_data_dir() / "data" / _CACHE_FILENAME


def load_auto_orden_cache() -> dict[str, str]:
    """Devuelve {escuela_id(str): marcador}. {} si no hay/está corrupto."""
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:  # noqa: BLE001
        pass
    return {}


def save_auto_orden_cache(cache: dict[str, str]) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({str(k): str(v) for k, v in cache.items()}, ensure_ascii=False),
        encoding="utf-8",
    )
