"""Validaciones puras de la ventana de una talla (editar o duplicar).

Tanda 5 del alta (2026-11-15): se quitaron las del asistente viejo de la
prenda (pasos, modo «ropa normal», lote de tallas), que se retiró.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

def _parse_price(raw_price: object) -> Decimal | None:
    """El precio como número, o None si el texto no es un número («$199», «1,200»)."""
    try:
        value = Decimal(str(raw_price or "").strip())
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def non_numeric_catalog_prices(prices_by_size: dict[str, str]) -> list[str]:
    """Tallas cuyo precio no es un número (lleva «$», comas o letras)."""
    return [
        str(size)
        for size, raw_price in prices_by_size.items()
        if str(raw_price or "").strip() and _parse_price(raw_price) is None
    ]


def invalid_catalog_prices(prices_by_size: dict[str, str]) -> list[str]:
    """Tallas cuyo precio es un número en $0 o negativo."""
    invalid: list[str] = []
    for size, raw_price in prices_by_size.items():
        value = _parse_price(raw_price)
        if value is not None and value <= 0:
            invalid.append(str(size))
    return invalid


SOLO_NUMERO = "Escribe solo el número, por ejemplo 199 (sin $ ni comas)."


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
    if non_numeric_catalog_prices({"precio": str(payload.get("precio"))}):
        return f"El precio de venta no es un número. {SOLO_NUMERO}"
    if invalid_catalog_prices({"precio": str(payload.get("precio"))}):
        return "El precio de venta no puede quedar en $0 ni ser negativo."
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
