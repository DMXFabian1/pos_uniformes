"""Almacenamiento local de presupuestos generados sin conexion.

Los presupuestos se guardan en un JSON junto al ejecutable. No se
sincronizan automaticamente a la DB — son locales al satelite.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_FILENAME = "offline_quotes.json"


def _path() -> Path:
    return satellite_data_dir() / "data" / _FILENAME


def _load_raw() -> list[dict]:
    path = _path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def _save_raw(quotes: list[dict]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(quotes, ensure_ascii=False, default=str), encoding="utf-8")


def save_offline_quote(
    *,
    folio: str,
    client_name: str,
    client_phone: str,
    notes: str,
    validity_date: object,
    cart: list[dict],
    total: object,
) -> None:
    quotes = _load_raw()
    quotes.append({
        "folio": folio,
        "client_name": client_name,
        "client_phone": client_phone,
        "notes": notes,
        "validity_date": str(validity_date) if validity_date else "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total": str(Decimal(str(total)).quantize(Decimal("0.01"))),
        "cart": [
            {
                "sku": str(item.get("sku", "")),
                "producto_nombre": str(item.get("producto_nombre", "")),
                "cantidad": int(item.get("cantidad", 1)),
                "precio_unitario": str(Decimal(str(item.get("precio_unitario", "0"))).quantize(Decimal("0.01"))),
                "talla": str(item.get("talla") or ""),
                "nivel_educativo_nombre": str(item.get("nivel_educativo_nombre") or ""),
                "escuela_nombre": str(item.get("escuela_nombre") or ""),
            }
            for item in cart
        ],
    })
    _save_raw(quotes)


def list_offline_quotes() -> list[dict]:
    return list(reversed(_load_raw()))


def delete_offline_quote(folio: str) -> None:
    quotes = _load_raw()
    _save_raw([q for q in quotes if q.get("folio") != folio])


def get_offline_quote(folio: str) -> dict | None:
    return next((q for q in _load_raw() if q.get("folio") == folio), None)
