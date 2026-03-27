"""Helpers puros para paginar el listado visible de Catalogo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogPaginationView:
    page_rows: list[dict[str, object]]
    current_page_index: int
    total_pages: int
    total_rows: int
    start_row_number: int
    end_row_number: int
    page_label: str
    previous_enabled: bool
    next_enabled: bool


def build_catalog_pagination_view(
    filtered_rows: list[dict[str, object]],
    *,
    current_page_index: int,
    page_size: int,
) -> CatalogPaginationView:
    if page_size <= 0:
        raise ValueError("page_size debe ser mayor a cero.")

    total_rows = len(filtered_rows)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    normalized_page_index = min(max(current_page_index, 0), total_pages - 1)
    start_index = normalized_page_index * page_size
    end_index = start_index + page_size
    visible_end = min(end_index, total_rows)
    page_rows = filtered_rows[start_index:end_index]

    if total_rows == 0:
        start_row_number = 0
        end_row_number = 0
        page_label = "0 de 0 | p. 1/1"
    else:
        start_row_number = start_index + 1
        end_row_number = visible_end
        page_label = f"{start_row_number}-{end_row_number} de {total_rows} | p. {normalized_page_index + 1}/{total_pages}"

    return CatalogPaginationView(
        page_rows=page_rows,
        current_page_index=normalized_page_index,
        total_pages=total_pages,
        total_rows=total_rows,
        start_row_number=start_row_number,
        end_row_number=end_row_number,
        page_label=page_label,
        previous_enabled=normalized_page_index > 0,
        next_enabled=normalized_page_index < total_pages - 1,
    )
