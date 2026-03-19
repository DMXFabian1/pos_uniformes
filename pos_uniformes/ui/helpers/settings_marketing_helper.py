"""Helpers visibles para el resumen de marketing en Configuracion."""

from __future__ import annotations

def _normalize_loyalty_level(loyalty_level: object) -> str:
    if hasattr(loyalty_level, "value"):
        return str(getattr(loyalty_level, "value"))
    return str(loyalty_level)


def build_settings_marketing_summary_label(loyalty_levels: list[object]) -> str:
    counts = {
        "BASICO": 0,
        "LEAL": 0,
        "PROFESOR": 0,
        "MAYORISTA": 0,
    }
    for loyalty_level in loyalty_levels:
        normalized_level = _normalize_loyalty_level(loyalty_level)
        counts[normalized_level] = counts.get(normalized_level, 0) + 1

    return (
        f"Clientes registrados: {len(loyalty_levels)}\n"
        f"BASICO: {counts['BASICO']} | "
        f"LEAL: {counts['LEAL']} | "
        f"PROFESOR: {counts['PROFESOR']} | "
        f"MAYORISTA: {counts['MAYORISTA']}"
    )
