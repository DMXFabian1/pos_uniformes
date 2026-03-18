"""Helpers visibles para el resumen del historial de caja en Configuracion."""

from __future__ import annotations


def build_settings_cash_history_status_label(
    *,
    total_sessions: int,
    open_sessions: int,
    closed_sessions: int,
    date_from_iso: str,
    date_to_iso: str,
) -> str:
    return (
        f"Cortes registrados: {total_sessions} | Abiertas: {open_sessions} | "
        f"Cerradas: {closed_sessions} | Rango: {date_from_iso} a {date_to_iso}"
    )
