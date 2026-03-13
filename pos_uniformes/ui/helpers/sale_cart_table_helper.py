"""Helpers puros para preparar el detalle visible del carrito de venta."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SaleCartTableRow:
    values: tuple[object, object, object, object, Decimal]


@dataclass(frozen=True)
class SaleCartTableView:
    rows: tuple[SaleCartTableRow, ...]
    total_items: int


def build_sale_cart_table_view(sale_cart: list[dict[str, object]]) -> SaleCartTableView:
    rows: list[SaleCartTableRow] = []
    total_items = 0
    for item in sale_cart:
        quantity = int(item["cantidad"])
        line_subtotal = Decimal(item["precio_unitario"]) * quantity
        total_items += quantity
        rows.append(
            SaleCartTableRow(
                values=(
                    item["sku"],
                    item["producto_nombre"],
                    quantity,
                    item["precio_unitario"],
                    line_subtotal,
                )
            )
        )
    return SaleCartTableView(rows=tuple(rows), total_items=total_items)
