"""Helpers visibles para el resumen del historial de caja en Configuracion."""

from __future__ import annotations

from datetime import date

from pos_uniformes.utils.date_format import format_display_date


def _normalize_date_label(value: str) -> str:
    try:
        return format_display_date(date.fromisoformat(value))
    except Exception:
        return value


def build_settings_cash_history_status_label(
    *,
    total_sessions: int,
    open_sessions: int,
    closed_sessions: int,
    date_from_iso: str,
    date_to_iso: str,
) -> str:
    date_from_label = _normalize_date_label(date_from_iso)
    date_to_label = _normalize_date_label(date_to_iso)
    return (
        f"Cortes registrados: {total_sessions} | Abiertas: {open_sessions} | "
        f"Cerradas: {closed_sessions} | Rango: {date_from_label} a {date_to_label}"
    )
