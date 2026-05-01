"""Cache local de preferencias de impresion de tickets.

Permite que el satelite imprima tickets sin conexion a la DB,
usando la configuracion guardada en el ultimo arranque online.
"""

from __future__ import annotations

import json
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_CACHE_FILENAME = "ticket_print_settings.json"


def _cache_path() -> Path:
    return satellite_data_dir() / "data" / _CACHE_FILENAME


def save_ticket_print_settings(ticket_printer: str, copies: int) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"ticket_printer": ticket_printer, "copies": copies}, ensure_ascii=False),
        encoding="utf-8",
    )


def load_ticket_print_settings() -> tuple[str, int]:
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        return str(data.get("ticket_printer", "")), int(data.get("copies", 1))
    except Exception:  # noqa: BLE001
        return "", 1
