"""Helpers puros para mensajes de transicion de lealtad en venta."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable


def build_sale_loyalty_transition_notice(
    *,
    client_name: str,
    previous_label: str,
    new_label: str,
    new_discount: Decimal | str | int | float,
    format_discount_label: Callable[[Decimal | str | int | float], str],
) -> str:
    normalized_name = client_name.strip() or "Este cliente"
    normalized_previous = previous_label.strip() or "nivel anterior"
    normalized_new = new_label.strip() or "nuevo nivel"
    discount_label = format_discount_label(Decimal(str(new_discount or 0)).quantize(Decimal("0.01")))
    if normalized_previous == normalized_new:
        return (
            f"{normalized_name} conserva el nivel {normalized_new}. "
            f"Su descuento vigente de {discount_label} seguira aplicando en la siguiente compra."
        )
    return (
        f"{normalized_name} cambia de {normalized_previous} a {normalized_new}. "
        f"El nuevo descuento de {discount_label} aplicara desde la siguiente compra."
    )
