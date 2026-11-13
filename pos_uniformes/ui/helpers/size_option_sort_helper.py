"""Orden natural para opciones de talla en filtros y combos.

El orden vive en `services/talla_orden_service.py` (puro y probado), que
comparten filtros, Bodega y la tabla de Inventario.
"""

from __future__ import annotations

from pos_uniformes.services.talla_orden_service import (
    ORDEN_LETRAS as _ALPHA_SIZE_ORDER,
    TALLAS_ESPECIALES,
    clave_talla,
    es_talla_numerica,
)

# Se conserva el nombre: bodega_service lo importa.
_size_sort_key = clave_talla


def sort_size_options(values: list[object]) -> list[str]:
    normalized_values = [str(value).strip() for value in values if str(value).strip()]
    return sorted(normalized_values, key=_size_sort_key)


def group_size_options(values: list[object]) -> list[tuple[str, list[str]]]:
    grouped: dict[str, list[str]] = {
        "Numericas": [],
        "Letras": [],
        "Especiales": [],
    }
    for raw_value in sort_size_options(values):
        group_name = _size_group_name(raw_value)
        grouped[group_name].append(raw_value)
    return [(group_name, items) for group_name, items in grouped.items() if items]


def _size_group_name(raw_value: str) -> str:
    normalized = raw_value.strip().upper()
    if es_talla_numerica(normalized):
        return "Numericas"
    if normalized in TALLAS_ESPECIALES:
        return "Especiales"
    if normalized in _ALPHA_SIZE_ORDER:
        return "Letras"
    return "Especiales"
