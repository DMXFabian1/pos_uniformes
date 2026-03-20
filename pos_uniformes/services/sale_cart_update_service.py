"""Actualizaciones puntuales del carrito de venta."""

from __future__ import annotations

from collections.abc import Callable


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
