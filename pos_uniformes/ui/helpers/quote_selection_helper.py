"""Seleccion y estado contextual de acciones en Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteActionState:
    cancel_enabled: bool


def resolve_selected_quote_id(table) -> int | None:
    selected_row = table.currentRow()
    if selected_row < 0:
        return None
    item = table.item(selected_row, 0)
    if item is None:
        return None
    quote_id = item.data(32)
    return int(quote_id) if quote_id is not None else None


def build_quote_action_state(*, can_sell: bool, has_selection: bool) -> QuoteActionState:
    return QuoteActionState(cancel_enabled=can_sell and has_selection)
