"""Helpers visibles para el resumen del listado de catalogo."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.services.active_filter_service import (
    build_active_filters_summary,
    build_filters_label,
)


@dataclass(frozen=True)
class CatalogSummaryView:
    results_summary: str
    active_filters_summary: str


def build_catalog_summary_view(
    *,
    total_rows: int,
    visible_rows: list[dict[str, object]],
    active_filter_labels: list[str],
) -> CatalogSummaryView:
    total_stock = sum(int(row["stock_actual"]) for row in visible_rows)
    reserved_count = sum(1 for row in visible_rows if int(row["apartado_cantidad"]) > 0)
    fallback_count = sum(1 for row in visible_rows if bool(row.get("fallback_importacion")))
    filters_label = build_filters_label(active_filter_labels)
    return CatalogSummaryView(
        results_summary=(
            f"Resultados: {len(visible_rows)} de {total_rows} | Stock visible: {total_stock} | "
            f"Con apartados: {reserved_count} | Fallbacks: {fallback_count} | Filtros: {filters_label}"
        ),
        active_filters_summary=build_active_filters_summary(active_filter_labels),
    )
