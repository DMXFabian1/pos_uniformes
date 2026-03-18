"""Helpers visibles para el resumen de filtros en Apartados."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.services.active_filter_service import (
    build_active_filter_labels,
    build_filters_label,
)


@dataclass(frozen=True)
class LayawaySummaryView:
    status_label: str
    active_filter_labels: list[str]


def build_layaway_summary_view(
    *,
    visible_rows: list[dict[str, object]],
    search_text: str,
    state_filter_value: object,
    state_filter_text: str,
    due_filter_value: object,
    due_filter_text: str,
) -> LayawaySummaryView:
    active_filter_labels = build_active_filter_labels(
        search_text=search_text,
        multi_filters=(),
        combo_filters=(
            ("estado", state_filter_value, state_filter_text),
            ("vencimiento", due_filter_value, due_filter_text),
        ),
    )
    pending_total = sum(Decimal(row["saldo"]) for row in visible_rows)
    if visible_rows:
        status_label = (
            f"Apartados visibles: {len(visible_rows)} | Pendiente total: ${pending_total} | "
            f"Filtros: {build_filters_label(active_filter_labels)}"
        )
    elif active_filter_labels:
        status_label = "No hay apartados con esos filtros."
    else:
        status_label = "No hay apartados recientes."
    return LayawaySummaryView(
        status_label=status_label,
        active_filter_labels=active_filter_labels,
    )
