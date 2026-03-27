"""Seleccion y estado contextual de acciones en Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteActionState:
    cancel_enabled: bool
    whatsapp_enabled: bool


# Qt.ItemDataRole.UserRole sin depender de PyQt6 en pruebas puras.
QUOTE_ROW_ID_ROLE = 0x0100


def resolve_selected_quote_id(table) -> int | None:
    selected_row = getattr(table, "currentRow", lambda: -1)()
    if selected_row < 0:
        return None
    item = table.item(selected_row, 0)
    if item is None:
        return None
    quote_id = item.data(QUOTE_ROW_ID_ROLE)
    return int(quote_id) if quote_id is not None else None


def build_quote_action_state(
    *,
    can_sell: bool,
    has_selection: bool,
    selected_state: str,
    has_phone: bool,
) -> QuoteActionState:
    normalized_state = selected_state.strip().upper()
    is_active = normalized_state in {"BORRADOR", "EMITIDO"}
    return QuoteActionState(
        cancel_enabled=can_sell and has_selection and is_active,
        whatsapp_enabled=has_selection and is_active and has_phone,
    )
