"""Helpers puros para preparar el detalle visible del carrito de venta."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SaleCartTableRow:
    values: tuple[object, object, object, Decimal]


@dataclass(frozen=True)
class SaleCartTableView:
    rows: tuple[SaleCartTableRow, ...]
    total_items: int


def _strikethrough(text: str) -> str:
    """Aplica tachado Unicode (U+0336) a cada carácter."""
    return "".join(c + "̶" for c in text)


def build_sale_cart_table_view(sale_cart: list[dict[str, object]]) -> SaleCartTableView:
    rows: list[SaleCartTableRow] = []
    total_items = 0
    for item in sale_cart:
        quantity = int(item["cantidad"])
        unit_price = Decimal(item["precio_unitario"])
        line_subtotal = unit_price * quantity
        total_items += quantity
        display_name = str(item["producto_nombre"])
        pricing_label = str(item.get("pricing_rule_label") or "").strip()
        if pricing_label:
            base_price = Decimal(item.get("precio_base", unit_price))
            if base_price != unit_price:
                struck = _strikethrough(f"${base_price}")
                display_name += f"\n{struck} → ${unit_price} {pricing_label}"
        rows.append(
            SaleCartTableRow(
                values=(
                    quantity,
                    display_name,
                    item["precio_unitario"],
                    line_subtotal,
                )
            )
        )
    return SaleCartTableView(rows=tuple(rows), total_items=total_items)
