"""Estado visible del panel de Caja a partir del carrito ya calculado."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.ui.helpers.sale_cashier_view_helper import SaleCashierView, build_sale_cashier_view
from pos_uniformes.ui.helpers.sale_payment_summary_helper import build_sale_payment_tooltip


@dataclass(frozen=True)
class SaleCashierPanelView:
    cashier_view: SaleCashierView
    payment_tooltip: str
    remove_enabled: bool
    clear_enabled: bool


def build_sale_cashier_panel_view(
    *,
    sale_cart: list[dict[str, object]],
    subtotal: Decimal,
    applied_discount: Decimal,
    rounding_adjustment: Decimal,
    collected_total: Decimal,
    payment_method: str,
    winner_label: str,
    can_sell: bool,
) -> SaleCashierPanelView:
    normalized_payment_method = payment_method.strip() or "Efectivo"
    cashier_view = build_sale_cashier_view(
        sale_cart=sale_cart,
        subtotal=subtotal,
        applied_discount=applied_discount,
        rounding_adjustment=rounding_adjustment,
        collected_total=collected_total,
        payment_method=normalized_payment_method,
        winner_label=winner_label,
    )
    has_items = bool(sale_cart)
    return SaleCashierPanelView(
        cashier_view=cashier_view,
        payment_tooltip=build_sale_payment_tooltip(normalized_payment_method),
        remove_enabled=can_sell and has_items,
        clear_enabled=can_sell and has_items,
    )
