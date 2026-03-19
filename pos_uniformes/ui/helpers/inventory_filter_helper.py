"""Filtrado visible del listado de Inventario."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pos_uniformes.ui.helpers.listing_visibility_helper import (
    matches_active_state,
    matches_fallback_duplicate,
    matches_origin_legacy,
    matches_selected_values,
)


@dataclass(frozen=True)
class InventoryVisibleFilterState:
    search_text: str
    category_filters: tuple[str, ...]
    brand_filters: tuple[str, ...]
    school_filters: tuple[str, ...]
    type_filters: tuple[str, ...]
    piece_filters: tuple[str, ...]
    size_filters: tuple[str, ...]
    color_filters: tuple[str, ...]
    status_filter: str
    stock_filter: str
    qr_filter: str
    origin_filter: str
    duplicate_filter: str


def filter_visible_inventory_rows(
    snapshot_rows: list[dict[str, object]],
    *,
    filters: InventoryVisibleFilterState,
    search_matcher: Callable[[dict[str, object], str], bool],
) -> list[dict[str, object]]:
    visible_rows: list[dict[str, object]] = []
    for row in snapshot_rows:
        if inventory_row_matches_visible_filters(
            row,
            filters=filters,
            search_matcher=search_matcher,
        ):
            visible_rows.append(row)
    return visible_rows


def inventory_row_matches_visible_filters(
    row: dict[str, object],
    *,
    filters: InventoryVisibleFilterState,
    search_matcher: Callable[[dict[str, object], str], bool],
) -> bool:
    return (
        search_matcher(row, filters.search_text)
        and matches_selected_values(row["categoria_nombre"], filters.category_filters)
        and matches_selected_values(row["marca_nombre"], filters.brand_filters)
        and matches_selected_values(row["escuela_nombre"], filters.school_filters)
        and matches_selected_values(row["tipo_prenda_nombre"], filters.type_filters)
        and matches_selected_values(row["tipo_pieza_nombre"], filters.piece_filters)
        and matches_selected_values(row["talla"], filters.size_filters)
        and matches_selected_values(row["color"], filters.color_filters)
        and matches_active_state(bool(row["variante_activa"]), filters.status_filter)
        and _matches_inventory_stock_filter(int(row["stock_actual"]), filters.stock_filter)
        and _matches_inventory_qr_filter(bool(row["qr_exists"]), filters.qr_filter)
        and matches_origin_legacy(bool(row["origen_legacy"]), filters.origin_filter)
        and matches_fallback_duplicate(bool(row["fallback_importacion"]), filters.duplicate_filter)
    )


def _matches_inventory_stock_filter(stock_actual: int, stock_filter: str) -> bool:
    return (
        not stock_filter
        or (stock_filter == "zero" and stock_actual == 0)
        or (stock_filter == "low" and 0 < stock_actual <= 3)
        or (stock_filter == "available" and stock_actual > 0)
    )


def _matches_inventory_qr_filter(qr_exists: bool, qr_filter: str) -> bool:
    return (
        not qr_filter
        or (qr_filter == "ready" and qr_exists)
        or (qr_filter == "missing" and not qr_exists)
    )
