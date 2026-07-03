"""Cache local de la info del negocio para tickets offline.

Espejo de ticket_print_settings_cache_service: permite armar tickets sin
pegar a la DB. Cuando el satelite esta offline, get_session() bloquea hasta
el connect_timeout (5s) en cada ticket; este cache lo evita guardando el
nombre/telefono/direccion del ultimo arranque online.
"""

from __future__ import annotations

import json
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_CACHE_FILENAME = "business_info.json"


def _cache_path() -> Path:
    return satellite_data_dir() / "data" / _CACHE_FILENAME


def save_business_info(nombre: str, telefono: str, direccion: str) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"nombre": nombre, "telefono": telefono, "direccion": direccion},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def load_business_info() -> tuple[str, str, str] | None:
    """Devuelve (nombre, telefono, direccion) o None si no hay cache valido."""
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        return (
            str(data.get("nombre", "")),
            str(data.get("telefono", "")),
            str(data.get("direccion", "")),
        )
    except Exception:  # noqa: BLE001
        return None
