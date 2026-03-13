"""Helpers puros para opciones de descuento manual en caja."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable


def build_sale_discount_options(
    *,
    preset_values: list[Decimal | str | int | float],
    current_discount: Decimal | str | int | float,
    normalize_discount_value: Callable[[object | None], Decimal],
    format_discount_label: Callable[[Decimal | str | int | float], str],
) -> list[tuple[str, Decimal]]:
    normalized_current = normalize_discount_value(current_discount)
    options: list[tuple[str, Decimal]] = [("Sin descuento", Decimal("0.00"))]

    for preset in preset_values:
        normalized_preset = normalize_discount_value(preset)
        options.append((format_discount_label(normalized_preset), normalized_preset))

    if normalized_current > Decimal("0.00"):
        options.append((f"Manual ({format_discount_label(normalized_current)})", normalized_current))

    deduped_options: list[tuple[str, Decimal]] = []
    seen_values: set[Decimal] = set()
    for label, value in options:
        normalized_value = normalize_discount_value(value)
        if normalized_value in seen_values:
            continue
        seen_values.add(normalized_value)
        deduped_options.append((label, normalized_value))
    return deduped_options


def expected_discount_option_label(
    discount_percent: Decimal | str | int | float,
    *,
    normalize_discount_value: Callable[[object | None], Decimal],
    format_discount_label: Callable[[Decimal | str | int | float], str],
) -> str:
    normalized = normalize_discount_value(discount_percent)
    if normalized == Decimal("0.00"):
        return "Sin descuento"
    return format_discount_label(normalized)
