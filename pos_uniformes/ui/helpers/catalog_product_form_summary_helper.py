"""Helpers puros para nombre visible y resumenes del formulario de producto."""

from __future__ import annotations


def build_catalog_product_display_name_preview(
    *,
    base_name: str,
    context_values: tuple[str, ...],
) -> str:
    """El nombre tal como se va a guardar.

    Usa la misma función que `CatalogService` (sin repetir la escuela y con
    las siglas en mayúsculas). Antes la vista previa tenía su propia lógica
    y le pegaba «| Tipo | Pieza» que el servicio ya no guarda desde la fase 1:
    lo que se veía no era lo que se guardaba (tanda 1 del alta, 2026-11-13)."""
    from pos_uniformes.services.catalog_service import CatalogService

    normalized_base_name = base_name.strip()
    if not normalized_base_name:
        return "Nombre final pendiente."

    # context_values = (escuela, tipo_prenda, tipo_pieza); tipo y pieza ya no
    # forman parte del nombre.
    school = str(context_values[0] or "").strip() if len(context_values) > 0 else ""
    return CatalogService.armar_nombre(normalized_base_name, school or None) or "Nombre final pendiente."


def build_catalog_variant_examples_preview(
    *,
    sizes: list[str],
    colors: list[str],
    default_size: str,
    default_color: str,
    max_items: int = 4,
) -> str:
    normalized_sizes = sizes or [default_size]
    normalized_colors = colors or [default_color]
    examples: list[str] = []
    for size in normalized_sizes:
        for color in normalized_colors:
            examples.append(f"{size} / {color}")
            if len(examples) >= max_items:
                return ", ".join(examples)
    return ", ".join(examples)


def build_catalog_capture_summary_html(
    *,
    final_name: str,
    total_variants: int,
    sku_summary: str,
    variant_examples: str,
    price_summary: str,
    stock_text: str,
    notes: list[str],
) -> str:
    return (
        "<div><b>Resumen en vivo</b></div>"
        f"<div><b>Producto:</b> {final_name}</div>"
        f"<div><b>Presentaciones previstas:</b> {total_variants}</div>"
        f"<div><b>SKU previstos:</b> {sku_summary}</div>"
        "<div><b>QR:</b> Manual bajo demanda. Puedes generarlo al final o desde Inventario.</div>"
        f"<div><b>Ejemplos:</b> {variant_examples}</div>"
        f"<div><b>Precio / stock inicial:</b> {price_summary} / {stock_text}</div>"
        f"<div style='color:#7e3a22;'>{' | '.join(notes) if notes else 'Listo para guardar el producto y crear el lote de presentaciones.'}</div>"
    )


def build_catalog_review_details_html(
    *,
    product_name: str,
    category_label: str,
    brand_label: str,
    context_values: tuple[str, ...],
    context_empty_label: str,
    sizes_preview: str,
    colors_preview: str,
    sku_summary: str,
    price_summary: str,
    stock_value: int,
    review_notes: list[str],
) -> str:
    context_text = " | ".join(value for value in context_values if value) or context_empty_label
    return (
        "<div><b>Revision final</b></div>"
        f"<div><b>Producto:</b> {product_name}</div>"
        f"<div><b>Categoria / marca:</b> {category_label} / {brand_label}</div>"
        f"<div><b>Contexto:</b> {context_text}</div>"
        f"<div><b>Tallas:</b> {sizes_preview}</div>"
        f"<div><b>Colores:</b> {colors_preview}</div>"
        f"<div><b>SKU previstos:</b> {sku_summary}</div>"
        "<div><b>QR:</b> Quedara pendiente. Puedes generarlo al terminar el lote o despues desde Inventario.</div>"
        f"<div><b>Precio / stock:</b> {price_summary} / {stock_value}</div>"
        f"<div style='color:#7e3a22;'>{' | '.join(review_notes) if review_notes else 'Todo listo para guardar.'}</div>"
    )
