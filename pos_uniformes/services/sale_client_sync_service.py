"""Helpers puros para sincronizar descuento cuando cambia el cliente en caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable


@dataclass(frozen=True)
class SaleClientSyncState:
    locked: bool
    discount_percent: Decimal
    source_label: str


def resolve_sale_client_sync_state(
    *,
    has_selected_client: bool,
    discount_percent: Decimal | str | int | float,
    source_label: str,
    normalize_discount_value: Callable[[object | None], Decimal],
) -> SaleClientSyncState:
    if not has_selected_client:
        return SaleClientSyncState(
            locked=False,
            discount_percent=Decimal("0.00"),
            source_label="",
        )

    return SaleClientSyncState(
        locked=True,
        discount_percent=normalize_discount_value(discount_percent),
        source_label=source_label.strip(),
    )
