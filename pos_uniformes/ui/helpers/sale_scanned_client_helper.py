"""Helpers visibles para el flujo de cliente escaneado en caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from pos_uniformes.services.scanned_client_flow_service import (
    ScannedClientFeedback,
    build_client_already_linked_feedback,
    build_replace_client_confirmation,
    build_scanned_client_applied_feedback,
    build_scanned_client_kept_feedback,
    decide_scanned_client_action,
)


@dataclass(frozen=True)
class SaleScannedClientUiState:
    action: str
    confirmation_message: str = ""
    immediate_feedback: ScannedClientFeedback | None = None
    rejected_feedback: ScannedClientFeedback | None = None
    applied_feedback: ScannedClientFeedback | None = None


def build_sale_scanned_client_ui_state(
    *,
    current_client_id: int | str | None,
    current_client_label: str,
    scanned_client_id: int | str,
    scanned_client_code: str,
    scanned_client_name: str,
    has_sale_cart: bool,
    discount_percent: Decimal | str | int | float,
    format_discount_label: Callable[[Decimal | str | int | float], str],
) -> SaleScannedClientUiState:
    decision = decide_scanned_client_action(
        current_client_id=current_client_id,
        scanned_client_id=scanned_client_id,
        has_sale_cart=has_sale_cart,
    )
    applied_feedback = build_scanned_client_applied_feedback(
        client_code=scanned_client_code,
        client_name=scanned_client_name,
        discount_percent=discount_percent,
        format_discount_label=format_discount_label,
    )
    if decision.action == "already_linked":
        return SaleScannedClientUiState(
            action=decision.action,
            immediate_feedback=ScannedClientFeedback(
                message=build_client_already_linked_feedback(scanned_client_code),
                tone="neutral",
                auto_clear_ms=1700,
            ),
        )
    if decision.action == "confirm_replace":
        return SaleScannedClientUiState(
            action=decision.action,
            confirmation_message=build_replace_client_confirmation(
                current_label=current_client_label.strip() or "Cliente actual",
                scanned_client_code=scanned_client_code,
                scanned_client_name=scanned_client_name,
            ),
            rejected_feedback=ScannedClientFeedback(
                message=build_scanned_client_kept_feedback(),
                tone="warning",
                auto_clear_ms=2000,
            ),
            applied_feedback=applied_feedback,
        )
    return SaleScannedClientUiState(
        action=decision.action,
        applied_feedback=applied_feedback,
    )
