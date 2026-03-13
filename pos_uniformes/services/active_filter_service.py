"""Helpers puros para formatear filtros activos."""

from __future__ import annotations

from collections.abc import Iterable


def build_active_filter_labels(
    *,
    search_text: str,
    multi_filters: Iterable[tuple[str, list[str]]],
    combo_filters: Iterable[tuple[str, object, str]],
) -> list[str]:
    active_filters: list[str] = []
    normalized_search = search_text.strip()
    if normalized_search:
        active_filters.append(f'texto="{normalized_search}"')

    for label, selected_labels in multi_filters:
        if selected_labels:
            active_filters.append(f"{label}={', '.join(selected_labels)}")

    for label, current_data, current_text in combo_filters:
        if current_data:
            active_filters.append(f"{label}={current_text}")

    return active_filters


def build_active_filters_summary(active_filters: list[str]) -> str:
    if not active_filters:
        return "Filtros activos: ninguno"
    return f"Filtros activos: {' | '.join(active_filters)}"


def build_filters_label(active_filters: list[str]) -> str:
    return ", ".join(active_filters) if active_filters else "sin filtros"
