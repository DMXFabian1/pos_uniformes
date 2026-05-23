"""Actualizaciones puntuales del carrito de venta."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from pos_uniformes.utils.product_name import build_ticket_product_name


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


def add_sale_cart_manual_line(
    sale_cart: list[dict[str, object]],
    *,
    description: str,
    unit_price: Decimal | str | int | float,
    quantity: int = 1,
) -> dict[str, object]:
    normalized_quantity = int(quantity)
    if normalized_quantity <= 0:
        raise ValueError("La cantidad debe ser mayor a cero.")
    normalized_description = str(description or "").strip() or "Venta manual"
    normalized_unit_price = Decimal(str(unit_price)).quantize(Decimal("0.01"))
    if normalized_unit_price <= Decimal("0.00"):
        raise ValueError("El precio debe ser mayor a cero.")

    line_item = {
        "line_type": "MANUAL",
        "sku": "SIN-CODIGO",
        "variante_id": None,
        "producto_nombre": normalized_description,
        "descripcion_snapshot": normalized_description,
        "cantidad": normalized_quantity,
        "precio_unitario": normalized_unit_price,
        "precio_base": normalized_unit_price,
        "pricing_rule_key": "",
        "pricing_rule_label": "",
    }
    sale_cart.append(line_item)
    return line_item


def add_sale_cart_variants(
    sale_cart: list[dict[str, object]],
    *,
    variants: list[object] | tuple[object, ...],
    quantity: int,
    stock_validator: Callable | None = None,
    line_overrides_by_sku: dict[str, dict[str, object]] | None = None,
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
                line_override=(line_overrides_by_sku or {}).get(sku),
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
    if str(line_item.get("line_type") or "").upper() == "MANUAL":
        line_item["cantidad"] = int(new_quantity)
        return line_item

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
    existing_total = _current_sale_cart_quantity(sale_cart, sku)
    current_line_quantity = int(line_item.get("cantidad", 0))
    validator(variante, (existing_total - current_line_quantity) + int(new_quantity))

    line_item["cantidad"] = int(new_quantity)
    return line_item


def _current_sale_cart_quantity(sale_cart: list[dict[str, object]], sku: str) -> int:
    return sum(
        int(item.get("cantidad", 0))
        for item in sale_cart
        if str(item.get("sku") or "").strip().upper() == sku
    )


def _apply_sale_cart_variant(
    sale_cart: list[dict[str, object]],
    *,
    variante,
    quantity: int,
    line_override: dict[str, object] | None = None,
) -> dict[str, object]:
    sku = str(getattr(variante, "sku", "") or "").strip().upper()
    pricing_rule_key = str((line_override or {}).get("pricing_rule_key") or "")
    existing = next(
        (
            item
            for item in sale_cart
            if str(item.get("sku") or "").strip().upper() == sku
            and str(item.get("pricing_rule_key") or "") == pricing_rule_key
        ),
        None,
    )
    unit_price = Decimal(str((line_override or {}).get("precio_unitario", getattr(variante, "precio_venta", 0))))
    base_price = Decimal(str((line_override or {}).get("precio_base", getattr(variante, "precio_venta", 0))))
    if existing is None:
        line_item = {
            "sku": sku,
            "variante_id": getattr(variante, "id", None),
            "producto_nombre": build_ticket_product_name(getattr(variante, "producto", None)),
            "talla": str(getattr(variante, "talla", "") or "-"),
            "cantidad": int(quantity),
            "precio_unitario": unit_price,
            "precio_base": base_price,
            "pricing_rule_key": pricing_rule_key,
            "pricing_rule_label": str((line_override or {}).get("pricing_rule_label") or ""),
        }
        sale_cart.append(line_item)
        return line_item

    existing["cantidad"] = int(existing.get("cantidad", 0)) + int(quantity)
    return existing
