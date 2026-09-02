"""Meta semanal de comisiones para la Libreta.

Config local por terminal (JSON junto a los demás cachés del satélite): el
dueño la fija desde su vista de la Libreta y cada empleada ve su barra de
progreso contra ella. 0 = sin meta (la barra no se muestra).
"""

from __future__ import annotations

import json
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_DATA_SUBDIR = "data"
_META_FILENAME = "libreta_meta.json"


def _meta_path() -> Path:
    return satellite_data_dir() / _DATA_SUBDIR / _META_FILENAME


def load_meta_semanal() -> int:
    path = _meta_path()
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = int(payload.get("meta_semanal", 0))
        return value if value >= 0 else 0
    except Exception:  # noqa: BLE001 — config corrupta = sin meta, no crash
        return 0


def save_meta_semanal(value: int) -> None:
    path = _meta_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"meta_semanal": max(0, int(value))}, ensure_ascii=False),
        encoding="utf-8",
    )
