"""Payloads y validaciones puras para los dialogos de catalogo."""

from __future__ import annotations


def validate_catalog_product_base_step(
    *,
    category_id: object,
    category_name: str,
    brand_id: object,
    base_name: str,
) -> str | None:
    normalized_category_name = category_name.strip()
    if category_id is None and (
        not normalized_category_name or normalized_category_name.casefold().startswith("selecciona ")
    ):
        return "Selecciona una categoria antes de continuar."
    if brand_id is None:
        return "Selecciona una marca antes de continuar."
    if not base_name.strip():
        return "Captura o genera el nombre base antes de continuar."
    return None


def validate_catalog_product_presentations_step(
    *,
    has_variant_intent: bool,
    missing_prices: list[str],
) -> str | None:
    if has_variant_intent and missing_prices:
        return "Todavia faltan precios para algunas tallas o bloques. Revisa ese paso antes de continuar."
    return None


def validate_catalog_product_submission(payload: dict[str, object]) -> str | None:
    category_id = payload.get("categoria_id")
    brand_id = payload.get("marca_id")
    base_name = str(payload.get("nombre") or "")
    return validate_catalog_product_base_step(
        category_id=category_id,
        category_name=str(payload.get("categoria_nombre") or ""),
        brand_id=brand_id,
        base_name=base_name,
    )


def build_catalog_product_dialog_payload(
    *,
    mode_key: str,
    category_id: object,
    category_name: str,
    brand_id: object,
    base_name: str,
    school: str,
    garment_type: str,
    piece_type: str,
    attribute: str,
    education_level: str,
    gender: str,
    shield: str,
    location: str,
    description: str,
    sizes: list[str],
    colors: list[str],
    variant_price: str,
    price_mode: str,
    prices_by_size: dict[str, str],
    price_summary: str,
    variant_cost: str,
    initial_stock: int,
) -> dict[str, object]:
    normalized_mode = "regular" if str(mode_key).strip() == "regular" else "uniform"
    normalized_sizes = [str(value).strip() for value in sizes if str(value).strip()]
    normalized_colors = [str(value).strip() for value in colors if str(value).strip()]
    payload = {
        "modo_catalogo": normalized_mode,
        "categoria_id": category_id,
        "categoria_nombre": category_name.strip(),
        "marca_id": brand_id,
        "nombre": base_name.strip(),
        "escuela": school.strip() if normalized_mode == "uniform" else "",
        "tipo_prenda": garment_type.strip(),
        "tipo_pieza": piece_type.strip(),
        "atributo": attribute.strip(),
        "nivel_educativo": education_level.strip() if normalized_mode == "uniform" else "",
        "genero": gender.strip(),
        "escudo": shield.strip() if normalized_mode == "uniform" else "",
        "ubicacion": location.strip(),
        "descripcion": description.strip(),
        "tallas": normalized_sizes,
        "colores": normalized_colors,
        "precio_variante": variant_price.strip(),
        "precio_modo": str(price_mode or "single").strip() or "single",
        "precios_por_talla": {
            str(size).strip(): str(price).strip()
            for size, price in prices_by_size.items()
            if str(size).strip() and str(price).strip()
        },
        "resumen_precio": price_summary.strip(),
        "costo_variante": variant_cost.strip(),
        "stock_inicial_variante": int(initial_stock),
    }
    return payload


def validate_catalog_variant_submission(
    payload: dict[str, object],
    *,
    require_stock: bool,
) -> str | None:
    if not payload.get("producto_id"):
        return "Selecciona un producto."
    if not str(payload.get("talla") or "").strip():
        return "Captura una talla."
    if not str(payload.get("precio") or "").strip():
        return "Captura el precio de venta."
    if require_stock and int(payload.get("stock_inicial") or 0) < 0:
        return "El stock inicial no puede ser negativo."
    return None


def build_catalog_variant_dialog_payload(
    *,
    product_id: object,
    sku: str,
    size: str,
    color: str,
    price: str,
    cost: str,
    initial_stock: int,
) -> dict[str, object]:
    return {
        "producto_id": product_id,
        "sku": sku.strip(),
        "talla": size.strip(),
        "color": color.strip(),
        "precio": price.strip(),
        "costo": cost.strip(),
        "stock_inicial": int(initial_stock),
    }


def build_catalog_batch_variant_dialog_payload(
    *,
    sizes: list[str],
    colors: list[str],
    initial_price: str,
    pricing_mode: str,
    prices_by_size: dict[str, str] | None,
    price_summary: str,
    initial_cost: str,
    initial_stock: int,
) -> dict[str, object]:
    normalized_prices = {
        str(size).strip(): str(price).strip()
        for size, price in (prices_by_size or {}).items()
        if str(size).strip() and str(price).strip()
    }
    return {
        "tallas": [str(value).strip() for value in sizes if str(value).strip()],
        "colores": [str(value).strip() for value in colors if str(value).strip()],
        "precio": initial_price.strip(),
        "precio_modo": str(pricing_mode or "single").strip() or "single",
        "precios_por_talla": normalized_prices,
        "resumen_precio": price_summary.strip(),
        "costo": initial_cost.strip(),
        "stock_inicial": int(initial_stock),
    }
