"""Filtrado visible del listado de Inventario."""

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
class InventoryVisibleFilterState:
    search_text: str
    use_filter: str
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
    conteo_filter: str
    precio_filter: str


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
        _matches_inventory_use_filter(str(row["categoria_nombre"]), filters.use_filter)
        and matches_selected_values(row["categoria_nombre"], filters.category_filters)
        and matches_selected_values(row["marca_nombre"], filters.brand_filters)
        and matches_selected_values(row["escuela_nombre"], filters.school_filters)
        and matches_selected_values(row["tipo_prenda_nombre"], filters.type_filters)
        and matches_selected_values(row["tipo_pieza_nombre"], filters.piece_filters)
        and matches_selected_values(row["talla"], filters.size_filters)
        and matches_selected_values(row["color"], filters.color_filters)
        and matches_active_state(bool(row["variante_activa"]), filters.status_filter)
        and _matches_inventory_stock_filter(int(row["stock_actual"]), filters.stock_filter, stock_minimo=row.get("stock_minimo"))
        and _matches_inventory_qr_filter(bool(row["qr_exists"]), filters.qr_filter)
        and matches_origin_legacy(bool(row["origen_legacy"]), filters.origin_filter)
        and matches_fallback_duplicate(bool(row["fallback_importacion"]), filters.duplicate_filter)
        and _matches_inventory_conteo_filter(row.get("ultimo_conteo_at"), filters.conteo_filter)
        and _matches_inventory_precio_filter(row.get("precio_venta"), filters.precio_filter)
        and search_matcher(row, filters.search_text)
    )


def _matches_inventory_use_filter(category_name: str, use_filter: str) -> bool:
    normalized_category = _normalize_text(category_name)
    is_uniform_category = normalized_category in UNIFORM_CATEGORIES
    return (
        not use_filter
        or (use_filter == "school_only" and is_uniform_category)
        or (use_filter == "general_only" and normalized_category and not is_uniform_category)
    )


def _matches_inventory_stock_filter(stock_actual: int, stock_filter: str, *, stock_minimo: int | None = None) -> bool:
    below_min = stock_minimo is not None and stock_actual < stock_minimo
    return (
        not stock_filter
        or (stock_filter == "zero" and stock_actual == 0)
        or (stock_filter == "low" and 0 < stock_actual <= 3)
        or (stock_filter == "available" and stock_actual > 0)
        or (stock_filter == "below_min" and below_min)
    )


def _matches_inventory_conteo_filter(ultimo_conteo_at: object, conteo_filter: str) -> bool:
    if not conteo_filter:
        return True
    if conteo_filter == "never":
        return ultimo_conteo_at is None
    if ultimo_conteo_at is None:
        return False
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc)
    try:
        conteo_dt = ultimo_conteo_at if hasattr(ultimo_conteo_at, "tzinfo") else ultimo_conteo_at  # type: ignore[assignment]
        if conteo_dt.tzinfo is None:  # type: ignore[union-attr]
            conteo_dt = conteo_dt.replace(tzinfo=timezone.utc)  # type: ignore[union-attr]
        days_ago = (now - conteo_dt).days  # type: ignore[operator]
    except Exception:
        return True
    if conteo_filter == "recent":
        return days_ago <= 3
    if conteo_filter == "stale":
        return days_ago >= 8
    return True


def _matches_inventory_precio_filter(precio_venta: object, precio_filter: str) -> bool:
    if not precio_filter:
        return True
    try:
        precio = float(precio_venta)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
    if precio_filter == "under_100":
        return precio < 100
    if precio_filter == "100_199":
        return 100 <= precio <= 199
    if precio_filter == "200_499":
        return 200 <= precio <= 499
    if precio_filter == "500_plus":
        return precio >= 500
    return True


def _matches_inventory_qr_filter(qr_exists: bool, qr_filter: str) -> bool:
    return (
        not qr_filter
        or (qr_filter == "ready" and qr_exists)
        or (qr_filter == "missing" and not qr_exists)
    )


def _normalize_text(raw_value: object) -> str:
    if raw_value is None:
        return ""
    return str(raw_value).strip().lower()
