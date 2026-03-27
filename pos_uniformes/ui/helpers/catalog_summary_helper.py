"""Helpers visibles para el resumen del listado de catalogo."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.services.active_filter_service import (
    build_active_filters_summary,
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
    return CatalogSummaryView(
        results_summary=(
            f"{len(visible_rows)}/{total_rows} resultados | stock {total_stock} | "
            f"ap. {reserved_count} | fallbacks {fallback_count}"
        ),
        active_filters_summary=build_active_filters_summary(active_filter_labels),
    )
