"""Predicados compartidos para filtros visibles de listados."""

from __future__ import annotations


def matches_selected_values(row_value: object, selected_values: tuple[str, ...], *, fallback: str = "") -> bool:
    return not selected_values or str(row_value or fallback) in selected_values


def matches_active_state(is_active: bool, status_filter: str) -> bool:
    return (
        not status_filter
        or (status_filter == "active" and is_active)
        or (status_filter == "inactive" and not is_active)
    )


def matches_origin_legacy(origen_legacy: bool, origin_filter: str) -> bool:
    return (
        not origin_filter
        or (origin_filter == "legacy" and origen_legacy)
        or (origin_filter == "native" and not origen_legacy)
    )


def matches_fallback_duplicate(fallback_importacion: bool, duplicate_filter: str) -> bool:
    return (
        not duplicate_filter
        or (duplicate_filter == "fallback_only" and fallback_importacion)
        or (duplicate_filter == "fallback_exclude" and not fallback_importacion)
    )
