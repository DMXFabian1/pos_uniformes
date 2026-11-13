"""Helpers visibles para el resumen de marketing en Configuracion."""

from __future__ import annotations


def build_settings_marketing_summary_label(clientes: list[object]) -> str:
    """Resumen del diálogo de Marketing.

    2026-11-12: ya no reparte a los clientes por el nivel viejo (BASICO,
    LEAL, PROFESOR, MAYORISTA), que se retiró («el nivel viejo retíralo»,
    Daniel). Solo dice cuántos clientes hay.
    """
    return f"Clientes registrados: {len(clientes)}"
