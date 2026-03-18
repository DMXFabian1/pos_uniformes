"""Helpers visibles para el resumen de filtros en Historial."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.services.active_filter_service import (
    build_active_filter_labels,
    build_filters_label,
)


@dataclass(frozen=True)
class HistorySummaryView:
    status_label: str
    active_filter_labels: list[str]


def build_history_summary_view(
    *,
    visible_count: int,
    search_text: str,
    source_filter_value: object,
    source_filter_text: str,
    entity_filter_value: object,
    entity_filter_text: str,
    type_filter_value: object,
    type_filter_text: str,
    date_from_label: str,
    date_to_label: str,
) -> HistorySummaryView:
    active_filter_labels = build_active_filter_labels(
        search_text=search_text,
        multi_filters=(),
        combo_filters=(
            ("origen", source_filter_value, source_filter_text),
            ("entidad", entity_filter_value, entity_filter_text),
            ("tipo", type_filter_value, type_filter_text),
        ),
    )
    if date_from_label:
        active_filter_labels.append(f"desde={date_from_label}")
    if date_to_label:
        active_filter_labels.append(f"hasta={date_to_label}")

    if visible_count:
        status_label = f"Movimientos visibles: {visible_count} | Filtros: {build_filters_label(active_filter_labels)}"
    elif active_filter_labels:
        status_label = "No hay movimientos con esos filtros."
    else:
        status_label = "No hay movimientos recientes."
    return HistorySummaryView(
        status_label=status_label,
        active_filter_labels=active_filter_labels,
    )
