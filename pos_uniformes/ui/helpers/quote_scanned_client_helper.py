"""Helpers visibles para cliente escaneado dentro del satelite de presupuestos."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.services.scanned_client_flow_service import (
    build_client_already_linked_feedback,
    decide_scanned_client_action,
)


@dataclass(frozen=True)
class QuoteScannedClientUiState:
    action: str
    confirmation_message: str | None = None
    rejected_message: str | None = None
    immediate_message: str | None = None
    applied_message: str | None = None


def build_quote_scanned_client_ui_state(
    *,
    current_client_id: int | str | None,
    current_client_label: str,
    scanned_client_id: int | str,
    scanned_client_code: str,
    scanned_client_name: str,
    has_quote_cart: bool,
) -> QuoteScannedClientUiState:
    decision = decide_scanned_client_action(
        current_client_id=current_client_id,
        scanned_client_id=scanned_client_id,
        has_sale_cart=has_quote_cart,
    )
    if decision.action == "already_linked":
        return QuoteScannedClientUiState(
            action=decision.action,
            immediate_message=build_client_already_linked_feedback(scanned_client_code),
        )
    if decision.action == "confirm_replace":
        current_label = current_client_label.strip() or "Cliente actual"
        return QuoteScannedClientUiState(
            action=decision.action,
            confirmation_message=(
                f"Ya hay un cliente asignado: {current_label}\n\n"
                f"Se escaneo {scanned_client_code} · {scanned_client_name}.\n"
                "Si continuas, el presupuesto quedara ligado al cliente nuevo.\n\n"
                "Deseas reemplazarlo?"
            ),
            rejected_message="Se conservo el cliente asignado al presupuesto.",
            applied_message=f"Cliente asignado: {scanned_client_code} · {scanned_client_name}.",
        )
    return QuoteScannedClientUiState(
        action=decision.action,
        applied_message=f"Cliente asignado: {scanned_client_code} · {scanned_client_name}.",
    )
