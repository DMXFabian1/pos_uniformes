"""Helpers visibles para la ficha breve de la seleccion actual en catalogo."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.utils.product_name import sanitize_product_display_name


@dataclass(frozen=True)
class CatalogSelectionView:
    selection_label: str


def resolve_catalog_row(
    catalog_rows: list[dict[str, object]],
    selected_row: int,
) -> dict[str, object] | None:
    if selected_row < 0 or selected_row >= len(catalog_rows):
        return None
    return catalog_rows[selected_row]


def build_empty_catalog_selection_view() -> CatalogSelectionView:
    return CatalogSelectionView(
        selection_label=(
            "Consulta catalogo general y separa rapido uniforme escolar o ropa normal. "
            "Despues afina por linea, pieza, talla, color o escuela."
        )
    )


def build_catalog_selection_view(
    *,
    is_admin: bool,
    sku: str,
    product_name: str,
    product_base_name: str,
    school_name: str,
    uniform_type_name: str,
    piece_type_name: str,
    sale_price: Decimal | str | int | float,
    stock_actual: int,
    layaway_reserved: int,
    variant_status: str,
    origin_label: str,
    origin_legacy: bool,
    legacy_name: str,
) -> CatalogSelectionView:
    clean_product_base_name = sanitize_product_display_name(product_base_name)
    context_parts = [str(school_name), str(uniform_type_name), str(piece_type_name)]
    context_text = " / ".join(part for part in context_parts if part and part != "-")
    compact_product_name = _truncate_catalog_label(clean_product_base_name, max_length=40)
    compact_context = _truncate_catalog_label(context_text or "General", max_length=34)
    compact_price = f"${sale_price}"
    if is_admin:
        admin_parts = [
            sku,
            compact_product_name,
            compact_context,
            compact_price,
            f"stock {stock_actual}",
            f"ap. {layaway_reserved}",
            str(variant_status),
        ]
        if str(origin_label).strip() and str(origin_label).strip().upper() != "NUEVO":
            admin_parts.append(str(origin_label))
        return CatalogSelectionView(
            selection_label=" | ".join(admin_parts)
        )
    return CatalogSelectionView(
        selection_label=(
            f"{compact_product_name} | {sku} | {compact_context} | "
            f"{compact_price} | stock {stock_actual}"
        )
    )


def build_catalog_selection_view_from_row(
    *,
    is_admin: bool,
    row: dict[str, object],
) -> CatalogSelectionView:
    return build_catalog_selection_view(
        is_admin=is_admin,
        sku=str(row["sku"]),
        product_name=str(row["producto_nombre"]),
        product_base_name=str(row["producto_nombre_base"]),
        school_name=str(row["escuela_nombre"]),
        uniform_type_name=str(row["tipo_prenda_nombre"]),
        piece_type_name=str(row["tipo_pieza_nombre"]),
        sale_price=row["precio_venta"],
        stock_actual=int(row["stock_actual"]),
        layaway_reserved=int(row["apartado_cantidad"]),
        variant_status=str(row["variante_estado"]),
        origin_label=str(row["origen_etiqueta"]),
        origin_legacy=bool(row["origen_legacy"]),
        legacy_name=str(row["nombre_legacy"] or ""),
    )


def find_catalog_row_index_by_variant_id(
    catalog_rows: list[dict[str, object]],
    variant_id: object,
) -> int | None:
    normalized_variant_id = _normalize_catalog_variant_id(variant_id)
    if normalized_variant_id is None:
        return None
    for row_index, row in enumerate(catalog_rows):
        if _normalize_catalog_variant_id(row.get("variante_id")) == normalized_variant_id:
            return row_index
    return None


def _normalize_catalog_variant_id(raw_variant_id: object) -> int | None:
    if raw_variant_id is None:
        return None
    try:
        return int(raw_variant_id)
    except (TypeError, ValueError):
        return None


def _truncate_catalog_label(value: str, *, max_length: int) -> str:
    clean_value = " ".join(str(value).split())
    if len(clean_value) <= max_length:
        return clean_value
    return clean_value[: max_length - 1].rstrip() + "…"
