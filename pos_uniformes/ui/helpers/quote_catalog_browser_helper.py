"""Helpers visibles para navegar catalogo simplificado en el satelite."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class QuoteCatalogBrowserRow:
    sku: str
    values: tuple[object, ...]


@dataclass(frozen=True)
class QuoteCatalogBrowserSummary:
    school_options: tuple[str, ...]
    level_options: tuple[str, ...]
    visible_count: int
    status_label: str


def build_quote_catalog_school_options(
    snapshot_rows: list[dict[str, object]],
    *,
    level_filter: str = "",
) -> tuple[str, ...]:
    normalized_level = level_filter.strip()
    schools = sorted(
        {
            str(row["escuela_nombre"]).strip()
            for row in snapshot_rows
            if str(row.get("escuela_nombre", "")).strip() and str(row["escuela_nombre"]).strip() != "General"
            and (
                not normalized_level
                or str(row.get("nivel_educativo_nombre", "")).strip() == normalized_level
            )
        }
    )
    return tuple(schools)


def build_quote_catalog_level_options(snapshot_rows: list[dict[str, object]]) -> tuple[str, ...]:
    levels = sorted(
        {
            str(row["nivel_educativo_nombre"]).strip()
            for row in snapshot_rows
            if str(row.get("nivel_educativo_nombre", "")).strip()
            and str(row["nivel_educativo_nombre"]).strip() != "Sin nivel"
        }
    )
    return tuple(levels)


def build_quote_catalog_browser(
    *,
    snapshot_rows: list[dict[str, object]],
    level_filter: str,
    school_filter: str,
    include_general: bool,
    search_text: str,
) -> tuple[tuple[QuoteCatalogBrowserRow, ...], QuoteCatalogBrowserSummary]:
    normalized_level = level_filter.strip()
    normalized_school = school_filter.strip()
    normalized_search = search_text.strip().lower()
    rows: list[QuoteCatalogBrowserRow] = []

    for row in snapshot_rows:
        if not bool(row.get("producto_activo")) or not bool(row.get("variante_activo")):
            continue

        row_level = str(row.get("nivel_educativo_nombre") or "Sin nivel").strip() or "Sin nivel"
        row_school = str(row.get("escuela_nombre") or "General").strip() or "General"
        if normalized_level and row_level != normalized_level:
            continue
        if normalized_school:
            matches_school = row_school == normalized_school
            matches_general = include_general and row_school == "General"
            if not matches_school and not matches_general:
                continue

        if normalized_search and normalized_search not in _searchable_text(row):
            continue

        rows.append(
            QuoteCatalogBrowserRow(
                sku=str(row["sku"]),
                values=(
                    row["sku"],
                    row["nivel_educativo_nombre"],
                    row["escuela_nombre"],
                    row["producto_nombre_base"],
                    row["tipo_prenda_nombre"],
                    row["talla"],
                    row["color"],
                    Decimal(str(row["precio_venta"])).quantize(Decimal("0.01")),
                ),
            )
        )

    status_parts = [f"{len(rows)} producto(s) visibles"]
    if normalized_level:
        status_parts.append(f"Nivel: {normalized_level}")
    if normalized_school:
        status_parts.append(f"Escuela: {normalized_school}")
        if include_general:
            status_parts.append("incluye extras generales")
    if normalized_search:
        status_parts.append(f"busqueda: {search_text.strip()}")

    summary = QuoteCatalogBrowserSummary(
        school_options=build_quote_catalog_school_options(snapshot_rows, level_filter=normalized_level),
        level_options=build_quote_catalog_level_options(snapshot_rows),
        visible_count=len(rows),
        status_label=" | ".join(status_parts),
    )
    return tuple(rows), summary


def _searchable_text(row: dict[str, object]) -> str:
    parts = (
        row.get("sku", ""),
        row.get("nivel_educativo_nombre", ""),
        row.get("escuela_nombre", ""),
        row.get("producto_nombre", ""),
        row.get("producto_nombre_base", ""),
        row.get("tipo_prenda_nombre", ""),
        row.get("tipo_pieza_nombre", ""),
        row.get("talla", ""),
        row.get("color", ""),
        row.get("producto_descripcion", ""),
    )
    return " ".join(str(part).strip().lower() for part in parts if str(part).strip())
