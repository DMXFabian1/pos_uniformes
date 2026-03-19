"""Seleccion y estado visible de acciones en ventas recientes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecentSaleActionState:
    ticket_enabled: bool
    cancel_enabled: bool


def resolve_selected_recent_sale_id(table) -> int | None:
    selected_row = table.currentRow()
    if selected_row < 0:
        return None
    sale_id_item = table.item(selected_row, 0)
    if sale_id_item is None:
        return None
    try:
        return int(sale_id_item.text())
    except (TypeError, ValueError):
        return None


def build_recent_sale_action_state(*, has_selection: bool, is_admin: bool) -> RecentSaleActionState:
    return RecentSaleActionState(
        ticket_enabled=has_selection,
        cancel_enabled=has_selection and is_admin,
    )
