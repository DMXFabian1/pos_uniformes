"""Cache local de ligas escuela-producto para el satélite offline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_LINKS_CACHE_FILENAME = "school_links_cache.json"
_DATA_SUBDIR = "data"


def _links_cache_path() -> Path:
    return satellite_data_dir() / _DATA_SUBDIR / _LINKS_CACHE_FILENAME


def save_school_links_cache(links: list[dict]) -> None:
    path = _links_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "links": links,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def load_school_links_cache() -> list[dict]:
    path = _links_cache_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        links = payload.get("links")
        return links if isinstance(links, list) else []
    except Exception:  # noqa: BLE001
        return []
