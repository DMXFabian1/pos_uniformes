"""Helpers visibles para el resumen de filtros en Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.services.active_filter_service import (
    build_active_filter_labels,
    build_filters_label,
)


@dataclass(frozen=True)
class QuoteSummaryView:
    status_label: str
    active_filter_labels: list[str]


def build_quote_summary_view(
    *,
    visible_count: int,
    search_text: str,
    state_filter_value: object,
    state_filter_text: str,
) -> QuoteSummaryView:
    active_filter_labels = build_active_filter_labels(
        search_text=search_text,
        multi_filters=(),
        combo_filters=(
            ("estado", state_filter_value, state_filter_text),
        ),
    )
    if visible_count:
        status_label = f"Presupuestos visibles: {visible_count} | Filtros: {build_filters_label(active_filter_labels)}"
    elif active_filter_labels:
        status_label = "No hay presupuestos con esos filtros."
    else:
        status_label = "No hay presupuestos recientes."
    return QuoteSummaryView(
        status_label=status_label,
        active_filter_labels=active_filter_labels,
    )
