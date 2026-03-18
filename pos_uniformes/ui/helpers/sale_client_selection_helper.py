"""Helpers visibles para el cambio de cliente en caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from pos_uniformes.services.sale_client_sync_service import SaleClientSyncState
from pos_uniformes.services.sale_discount_lock_service import (
    SaleDiscountLockState,
    build_sale_discount_lock_state,
    build_sale_discount_lock_tooltip,
)


@dataclass(frozen=True)
class SaleClientSelectionUiState:
    combo_discount_percent: Decimal | None
    clear_manual_promo: bool
    lock_state: SaleDiscountLockState
    lock_tooltip: str


def build_sale_client_selection_ui_state(
    *,
    sync_state: SaleClientSyncState,
    reset_manual: bool,
    normalize_discount_value: Callable[[object | None], Decimal],
    format_discount_label: Callable[[Decimal | str | int | float], str],
) -> SaleClientSelectionUiState:
    lock_state = build_sale_discount_lock_state(
        locked=sync_state.locked,
        discount_percent=sync_state.discount_percent,
        source_label=sync_state.source_label,
        normalize_discount_value=normalize_discount_value,
    )
    return SaleClientSelectionUiState(
        combo_discount_percent=Decimal("0.00") if reset_manual else None,
        clear_manual_promo=reset_manual,
        lock_state=lock_state,
        lock_tooltip=build_sale_discount_lock_tooltip(
            state=lock_state,
            format_discount_label=format_discount_label,
        ),
    )


def build_empty_sale_client_selection_ui_state(
    *,
    normalize_discount_value: Callable[[object | None], Decimal],
    format_discount_label: Callable[[Decimal | str | int | float], str],
) -> SaleClientSelectionUiState:
    return build_sale_client_selection_ui_state(
        sync_state=SaleClientSyncState(
            locked=False,
            discount_percent=Decimal("0.00"),
            source_label="",
        ),
        reset_manual=True,
        normalize_discount_value=normalize_discount_value,
        format_discount_label=format_discount_label,
    )
