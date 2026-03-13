"""Helpers puros para el bloqueo de descuento por cliente en caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable


@dataclass(frozen=True)
class SaleDiscountLockState:
    locked: bool
    discount_percent: Decimal
    source_label: str


def build_sale_discount_lock_state(
    *,
    locked: bool,
    discount_percent: Decimal | str | int | float,
    source_label: str,
    normalize_discount_value: Callable[[object | None], Decimal],
) -> SaleDiscountLockState:
    return SaleDiscountLockState(
        locked=bool(locked),
        discount_percent=normalize_discount_value(discount_percent),
        source_label=source_label.strip(),
    )


def build_sale_discount_lock_tooltip(
    *,
    state: SaleDiscountLockState,
    format_discount_label: Callable[[Decimal | str | int | float], str],
) -> str:
    if state.locked:
        source = state.source_label or "cliente"
        percent_label = format_discount_label(state.discount_percent)
        return (
            f"Promocion manual separada del beneficio de lealtad. Cliente actual: {source} ({percent_label}). "
            "No se acumula; se aplicara el mayor beneficio."
        )
    return "Aplica una promocion manual no acumulable. Si hay lealtad, se aplicara el mayor beneficio."
