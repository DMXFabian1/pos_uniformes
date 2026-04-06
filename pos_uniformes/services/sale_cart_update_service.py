"""Actualizaciones puntuales del carrito de venta."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from pos_uniformes.utils.product_name import sanitize_product_display_name


def add_sale_cart_variant(
    sale_cart: list[dict[str, object]],
    *,
    variante,
    quantity: int,
    stock_validator: Callable | None = None,
) -> dict[str, object]:
    updated_lines = add_sale_cart_variants(
        sale_cart,
        variants=[variante],
        quantity=quantity,
        stock_validator=stock_validator,
    )
    return updated_lines[0]


def add_sale_cart_variants(
    sale_cart: list[dict[str, object]],
    *,
    variants: list[object] | tuple[object, ...],
    quantity: int,
    stock_validator: Callable | None = None,
) -> list[dict[str, object]]:
    normalized_quantity = int(quantity)
    if normalized_quantity <= 0:
        raise ValueError("La cantidad debe ser mayor a cero.")
    if not variants:
        raise ValueError("No hay variantes para agregar al carrito.")

    if stock_validator is None:
        from pos_uniformes.services.venta_service import VentaService

        validator = VentaService.validar_stock_disponible
    else:
        validator = stock_validator

    increment_by_sku: dict[str, int] = {}
    variant_by_sku: dict[str, object] = {}
    ordered_skus: list[str] = []
    for variante in variants:
        sku = str(getattr(variante, "sku", "") or "").strip().upper()
        if not sku:
            raise ValueError("La variante seleccionada no tiene un SKU valido.")
        if sku not in increment_by_sku:
            ordered_skus.append(sku)
            increment_by_sku[sku] = 0
            variant_by_sku[sku] = variante
        increment_by_sku[sku] += normalized_quantity

    for sku in ordered_skus:
        target_quantity = _current_sale_cart_quantity(sale_cart, sku) + increment_by_sku[sku]
        validator(variant_by_sku[sku], target_quantity)

    updated_lines: list[dict[str, object]] = []
    for sku in ordered_skus:
        updated_lines.append(
            _apply_sale_cart_variant(
                sale_cart,
                variante=variant_by_sku[sku],
                quantity=increment_by_sku[sku],
            )
        )
    return updated_lines


def update_sale_cart_item_quantity(
    session,
    *,
    sale_cart: list[dict[str, object]],
    row_index: int,
    new_quantity: int,
    variant_loader: Callable | None = None,
    stock_validator: Callable | None = None,
) -> dict[str, object]:
    if row_index < 0 or row_index >= len(sale_cart):
        raise ValueError("Selecciona una linea valida del carrito.")
    if int(new_quantity) <= 0:
        raise ValueError("La cantidad debe ser mayor a cero.")

    line_item = sale_cart[row_index]
    sku = str(line_item.get("sku") or "").strip().upper()
    if not sku:
        raise ValueError("La linea seleccionada no tiene un SKU valido.")

    if variant_loader is None or stock_validator is None:
        from pos_uniformes.services.venta_service import VentaService

        loader = variant_loader or VentaService.obtener_variante_por_sku
        validator = stock_validator or VentaService.validar_stock_disponible
    else:
        loader = variant_loader
        validator = stock_validator
    variante = loader(session, sku)
    if variante is None:
        raise ValueError(f"El SKU '{sku}' ya no existe o esta inactivo.")
    validator(variante, int(new_quantity))

    line_item["cantidad"] = int(new_quantity)
    return line_item


def _current_sale_cart_quantity(sale_cart: list[dict[str, object]], sku: str) -> int:
    existing = next((item for item in sale_cart if str(item.get("sku") or "").strip().upper() == sku), None)
    return int(existing["cantidad"]) if existing is not None else 0


def _apply_sale_cart_variant(
    sale_cart: list[dict[str, object]],
    *,
    variante,
    quantity: int,
) -> dict[str, object]:
    sku = str(getattr(variante, "sku", "") or "").strip().upper()
    existing = next((item for item in sale_cart if str(item.get("sku") or "").strip().upper() == sku), None)
    if existing is None:
        line_item = {
            "sku": sku,
            "variante_id": getattr(variante, "id", None),
            "producto_nombre": sanitize_product_display_name(getattr(getattr(variante, "producto", None), "nombre", "")),
            "cantidad": int(quantity),
            "precio_unitario": Decimal(getattr(variante, "precio_venta", 0)),
        }
        sale_cart.append(line_item)
        return line_item

    existing["cantidad"] = int(existing.get("cantidad", 0)) + int(quantity)
    return existing
