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
    context_label: str
    status_label: str
    status_tone: str
    remove_enabled: bool
    clear_enabled: bool
    quick_adjust_enabled: bool


def build_sale_cashier_panel_view(
    *,
    sale_cart: list[dict[str, object]],
    subtotal: Decimal,
    applied_discount: Decimal,
    rounding_adjustment: Decimal,
    collected_total: Decimal,
    payment_method: str,
    winner_label: str,
    selected_client_label: str,
    can_sell: bool,
    has_cash_session: bool,
    is_processing: bool,
) -> SaleCashierPanelView:
    normalized_payment_method = payment_method.strip() or "Efectivo"
    normalized_client_label = selected_client_label.strip() or "Mostrador / sin cliente"
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
    if is_processing:
        status_label = "Procesando la venta actual."
        status_tone = "warning"
    elif not can_sell:
        status_label = "Modo solo lectura: tu rol no puede cobrar."
        status_tone = "warning"
    elif not has_cash_session:
        status_label = "Caja cerrada: abre caja antes de cobrar."
        status_tone = "danger"
    elif not has_items:
        status_label = "Escanea un SKU para empezar a vender."
        status_tone = "neutral"
    elif normalized_payment_method == "Transferencia":
        status_label = "Lista para cobrar por transferencia."
        status_tone = "positive"
    elif normalized_payment_method == "Mixto":
        status_label = "Lista para cobro mixto; revisa efectivo, transferencia y cambio."
        status_tone = "warning"
    else:
        status_label = "Lista para cobrar en efectivo."
        status_tone = "positive"
    return SaleCashierPanelView(
        cashier_view=cashier_view,
        payment_tooltip=build_sale_payment_tooltip(normalized_payment_method),
        context_label=(
            f"Cliente: {normalized_client_label} | "
            f"Pago: {normalized_payment_method} | "
            f"Descuento: {winner_label}"
        ),
        status_label=status_label,
        status_tone=status_tone,
        remove_enabled=can_sell and has_items,
        clear_enabled=can_sell and has_items,
        quick_adjust_enabled=can_sell and has_items,
    )
