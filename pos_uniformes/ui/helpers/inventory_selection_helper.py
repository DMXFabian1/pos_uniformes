"""Helpers puros para resolver seleccion y sincronizacion en Inventario."""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def resolve_selected_catalog_row(
    *,
    inventory_variant_id: object,
    catalog_table_row: int,
    catalog_rows: list[dict[str, object]],
) -> dict[str, object] | None:
    selected_from_inventory = find_catalog_row_by_variant_id(catalog_rows, inventory_variant_id)
    if selected_from_inventory is not None:
        return selected_from_inventory
    if catalog_table_row < 0 or catalog_table_row >= len(catalog_rows):
        return None
    return catalog_rows[catalog_table_row]


def find_catalog_row_by_variant_id(
    catalog_rows: list[dict[str, object]],
    variant_id: object,
) -> dict[str, object] | None:
    normalized_variant_id = normalize_inventory_variant_id(variant_id)
    if normalized_variant_id is None:
        return None
    return next(
        (
            row
            for row in catalog_rows
            if normalize_inventory_variant_id(row.get("variante_id")) == normalized_variant_id
        ),
        None,
    )


def collect_selected_inventory_variant_ids(raw_variant_ids: Iterable[object]) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for raw_variant_id in raw_variant_ids:
        normalized_variant_id = normalize_inventory_variant_id(raw_variant_id)
        if normalized_variant_id is None or normalized_variant_id in seen:
            continue
        seen.add(normalized_variant_id)
        ids.append(normalized_variant_id)
    return ids


def find_inventory_row_index_by_variant_id(
    row_variant_ids: Sequence[object],
    variant_id: object,
) -> int | None:
    normalized_variant_id = normalize_inventory_variant_id(variant_id)
    if normalized_variant_id is None:
        return None
    for row_index, row_variant_id in enumerate(row_variant_ids):
        if normalize_inventory_variant_id(row_variant_id) == normalized_variant_id:
            return row_index
    return None


def normalize_inventory_variant_id(raw_variant_id: object) -> int | None:
    if raw_variant_id is None:
        return None
    try:
        return int(raw_variant_id)
    except (TypeError, ValueError):
        return None
