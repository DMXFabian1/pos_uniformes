"""Estado contextual de acciones de Apartados."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayawayActionState:
    create_enabled: bool
    payment_enabled: bool
    deliver_enabled: bool
    cancel_enabled: bool
    receipt_enabled: bool
    sale_ticket_enabled: bool
    whatsapp_enabled: bool
    convert_sale_enabled: bool
    convert_sale_visible: bool


def build_layaway_action_state(
    *,
    can_manage_layaways: bool,
    can_operate_open_cash: bool,
    is_admin: bool,
    has_selected_layaway: bool,
    has_sale_cart: bool,
) -> LayawayActionState:
    return LayawayActionState(
        create_enabled=can_manage_layaways and can_operate_open_cash,
        payment_enabled=can_manage_layaways and can_operate_open_cash,
        deliver_enabled=can_manage_layaways and can_operate_open_cash,
        cancel_enabled=is_admin,
        receipt_enabled=can_manage_layaways,
        sale_ticket_enabled=can_manage_layaways and has_selected_layaway,
        whatsapp_enabled=can_manage_layaways and has_selected_layaway,
        convert_sale_enabled=can_manage_layaways and can_operate_open_cash and has_sale_cart,
        convert_sale_visible=can_manage_layaways,
    )
