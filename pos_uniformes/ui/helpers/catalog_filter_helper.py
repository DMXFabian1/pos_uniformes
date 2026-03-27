"""Filtrado visible del listado de Catalogo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pos_uniformes.ui.helpers.catalog_product_form_mode_helper import UNIFORM_CATEGORIES
from pos_uniformes.ui.helpers.listing_visibility_helper import (
    matches_active_state,
    matches_fallback_duplicate,
    matches_origin_legacy,
    matches_selected_values,
)


@dataclass(frozen=True)
class CatalogVisibleFilterState:
    search_text: str
    school_scope_filter: str
    category_filters: tuple[str, ...]
    brand_filters: tuple[str, ...]
    school_filters: tuple[str, ...]
    type_filters: tuple[str, ...]
    piece_filters: tuple[str, ...]
    size_filters: tuple[str, ...]
    color_filters: tuple[str, ...]
    status_filter: str
    stock_filter: str
    layaway_filter: str
    origin_filter: str
    duplicate_filter: str


def filter_visible_catalog_rows(
    snapshot_rows: list[dict[str, object]],
    *,
    filters: CatalogVisibleFilterState,
    search_matcher: Callable[[dict[str, object], str], bool],
) -> list[dict[str, object]]:
    return [
        row
        for row in snapshot_rows
        if catalog_row_matches_visible_filters(
            row,
            filters=filters,
            search_matcher=search_matcher,
        )
    ]


def catalog_row_matches_visible_filters(
    row: dict[str, object],
    *,
    filters: CatalogVisibleFilterState,
    search_matcher: Callable[[dict[str, object], str], bool],
) -> bool:
    return (
        _matches_catalog_school_scope(str(row["categoria_nombre"]), filters.school_scope_filter)
        and matches_selected_values(row["categoria_nombre"], filters.category_filters)
        and matches_selected_values(row["marca_nombre"], filters.brand_filters)
        and matches_selected_values(row["escuela_nombre"], filters.school_filters, fallback="General")
        and matches_selected_values(row["tipo_prenda_nombre"], filters.type_filters, fallback="-")
        and matches_selected_values(row["tipo_pieza_nombre"], filters.piece_filters, fallback="-")
        and matches_selected_values(row["talla"], filters.size_filters)
        and matches_selected_values(row["color"], filters.color_filters)
        and matches_active_state(bool(row["variante_activo"]), filters.status_filter)
        and _matches_catalog_stock_filter(
            stock_actual=int(row["stock_actual"]),
            apartado_cantidad=int(row["apartado_cantidad"]),
            stock_filter=filters.stock_filter,
        )
        and _matches_catalog_layaway_filter(
            apartado_cantidad=int(row["apartado_cantidad"]),
            layaway_filter=filters.layaway_filter,
        )
        and matches_origin_legacy(bool(row["origen_legacy"]), filters.origin_filter)
        and matches_fallback_duplicate(bool(row["fallback_importacion"]), filters.duplicate_filter)
        and search_matcher(row, filters.search_text)
    )


def _matches_catalog_stock_filter(
    *,
    stock_actual: int,
    apartado_cantidad: int,
    stock_filter: str,
) -> bool:
    return (
        not stock_filter
        or (stock_filter == "in_stock" and stock_actual > 0)
        or (stock_filter == "out_of_stock" and stock_actual == 0)
        or (stock_filter == "low_stock" and 0 < stock_actual <= 3)
        or (stock_filter == "available_over_reserved" and stock_actual > apartado_cantidad)
    )


def _matches_catalog_layaway_filter(*, apartado_cantidad: int, layaway_filter: str) -> bool:
    return (
        not layaway_filter
        or (layaway_filter == "reserved" and apartado_cantidad > 0)
        or (layaway_filter == "free" and apartado_cantidad == 0)
    )


def _matches_catalog_school_scope(categoria_nombre: str, school_scope_filter: str) -> bool:
    normalized_category = _normalize_text(categoria_nombre)
    is_uniform_category = normalized_category in UNIFORM_CATEGORIES
    return (
        not school_scope_filter
        or (school_scope_filter == "school_only" and is_uniform_category)
        or (school_scope_filter == "general_only" and normalized_category and not is_uniform_category)
    )


def _normalize_text(raw_value: object) -> str:
    if raw_value is None:
        return ""
    return str(raw_value).strip().lower()
