"""Helpers visibles para la ficha breve de la seleccion actual en catalogo."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CatalogSelectionView:
    selection_label: str


def build_empty_catalog_selection_view() -> CatalogSelectionView:
    return CatalogSelectionView(
        selection_label="Consulta uniformes y usa filtros macro como Deportivo, Oficial, Basico, Escolta o Accesorio."
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
    context_parts = [str(school_name), str(uniform_type_name), str(piece_type_name)]
    context_text = " | ".join(part for part in context_parts if part and part != "-")
    legacy_note = (
        f" | legacy: {legacy_name}"
        if origin_legacy and legacy_name and legacy_name != product_name
        else ""
    )
    if is_admin:
        return CatalogSelectionView(
            selection_label=(
                f"{sku} | {product_base_name} | {context_text or 'General'} | "
                f"precio {sale_price} | stock {stock_actual} | apartado {layaway_reserved} | "
                f"{variant_status} | {origin_label}{legacy_note}"
            )
        )
    return CatalogSelectionView(
        selection_label=(
            f"{product_base_name} | {sku} | {context_text or 'General'} | "
            f"precio {sale_price} | stock {stock_actual}"
        )
    )
