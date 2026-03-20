"""Orden natural para opciones de talla en filtros y combos."""

from __future__ import annotations

import re


_SIZE_RANGE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
_SIZE_NUMBER_RE = re.compile(r"^\s*(\d+)\s*$")
_ALPHA_SIZE_ORDER = {
    "CH": 10,
    "CH-MD": 15,
    "MD": 20,
    "GD": 30,
    "GD-EXG": 35,
    "EXG": 40,
    "UNI": 50,
    "UNITALLA": 60,
    "DAMA": 70,
    "ESP": 80,
}


def sort_size_options(values: list[object]) -> list[str]:
    normalized_values = [str(value).strip() for value in values if str(value).strip()]
    return sorted(normalized_values, key=_size_sort_key)


def _size_sort_key(raw_value: str) -> tuple[object, ...]:
    normalized = raw_value.strip().upper()

    range_match = _SIZE_RANGE_RE.match(normalized)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        return (0, start, 1, end, normalized)

    number_match = _SIZE_NUMBER_RE.match(normalized)
    if number_match:
        number = int(number_match.group(1))
        return (0, number, 0, number, normalized)

    if normalized in _ALPHA_SIZE_ORDER:
        return (1, _ALPHA_SIZE_ORDER[normalized], normalized)

    return (2, normalized)
