"""Helpers puros para preparar la vista visible de caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.ui.helpers.sale_cart_table_helper import SaleCartTableView, build_sale_cart_table_view
from pos_uniformes.ui.helpers.sale_cashier_summary_helper import SaleCashierSummary, build_sale_cashier_summary


@dataclass(frozen=True)
class SaleCashierView:
    table_view: SaleCartTableView
    summary: SaleCashierSummary


def build_sale_cashier_view(
    *,
    sale_cart: list[dict[str, object]],
    subtotal: Decimal,
    applied_discount: Decimal,
    rounding_adjustment: Decimal,
    collected_total: Decimal,
    payment_method: str,
    winner_label: str,
) -> SaleCashierView:
    table_view = build_sale_cart_table_view(sale_cart)
    summary = build_sale_cashier_summary(
        has_items=bool(sale_cart),
        lines_count=len(sale_cart),
        total_items=table_view.total_items,
        subtotal=subtotal,
        applied_discount=applied_discount,
        rounding_adjustment=rounding_adjustment,
        collected_total=collected_total,
        payment_method=payment_method,
        winner_label=winner_label,
    )
    return SaleCashierView(
        table_view=table_view,
        summary=summary,
    )
