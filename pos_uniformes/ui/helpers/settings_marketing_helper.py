"""Helpers visibles para el resumen de marketing en Configuracion."""

from __future__ import annotations

from pos_uniformes.database.models import NivelLealtad


def build_settings_marketing_summary_label(loyalty_levels: list[NivelLealtad]) -> str:
    counts = {
        NivelLealtad.BASICO: 0,
        NivelLealtad.LEAL: 0,
        NivelLealtad.PROFESOR: 0,
        NivelLealtad.MAYORISTA: 0,
    }
    for loyalty_level in loyalty_levels:
        counts[loyalty_level] = counts.get(loyalty_level, 0) + 1

    return (
        f"Clientes registrados: {len(loyalty_levels)}\n"
        f"BASICO: {counts[NivelLealtad.BASICO]} | "
        f"LEAL: {counts[NivelLealtad.LEAL]} | "
        f"PROFESOR: {counts[NivelLealtad.PROFESOR]} | "
        f"MAYORISTA: {counts[NivelLealtad.MAYORISTA]}"
    )
