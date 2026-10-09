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


def datos_del_negocio() -> tuple[str, str, str]:
    """(nombre, teléfono, dirección) para encabezar un ticket.

    La base manda y el cache es la red de abajo: sin esto, cada constructor
    de ticket cargaba lo suyo —uno el nombre y el teléfono por separado, otro
    los tres juntos— y los tickets de la misma tienda salían diciendo cosas
    distintas (2026-10-09, al homogeneizarlos).

    No avisa de la falta de conexión: eso lo hace Venta Rápida, que tiene
    pantalla para decirlo. Aquí el silencio es correcto porque hay cache.
    """
    try:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.business_settings_service import (
            BusinessSettingsService,
        )

        with get_session() as session:
            config = BusinessSettingsService.get_or_create(session)
            info = (
                config.nombre_negocio or "Uniformes",
                config.telefono or "",
                config.direccion or "",
            )
        try:
            save_business_info(*info)
        except Exception:  # noqa: BLE001 — sin cache, igual se imprime
            pass
        return info
    except Exception:  # noqa: BLE001 — sin base, lo del último arranque
        cache = load_business_info()
        return cache if cache and cache[0] else ("Uniformes", "", "")
