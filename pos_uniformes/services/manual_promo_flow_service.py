"""Reglas puras para el flujo de autorizacion de promo manual en caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.services.sale_discount_service import normalize_discount_value


@dataclass(frozen=True)
class ManualPromoState:
    authorized: bool
    authorized_percent: Decimal


@dataclass(frozen=True)
class ManualPromoDecision:
    action: str
    selected_percent: Decimal
    previous_state: ManualPromoState
    revert_percent: Decimal


def build_manual_promo_state(
    *,
    authorized: bool,
    authorized_percent: Decimal | str | int | float,
) -> ManualPromoState:
    normalized_percent = normalize_discount_value(authorized_percent)
    normalized_authorized = bool(authorized and normalized_percent > Decimal("0.00"))
    return ManualPromoState(
        authorized=normalized_authorized,
        authorized_percent=normalized_percent if normalized_authorized else Decimal("0.00"),
    )


def clear_manual_promo_state() -> ManualPromoState:
    return ManualPromoState(authorized=False, authorized_percent=Decimal("0.00"))


def current_manual_promo_percent(
    *,
    selected_percent: Decimal | str | int | float,
    state: ManualPromoState,
) -> Decimal:
    normalized_selected = normalize_discount_value(selected_percent)
    if not state.authorized:
        return Decimal("0.00")
    if normalized_selected != state.authorized_percent:
        return Decimal("0.00")
    return state.authorized_percent


def decide_manual_promo_change(
    *,
    selected_percent: Decimal | str | int | float,
    state: ManualPromoState,
) -> ManualPromoDecision:
    normalized_selected = normalize_discount_value(selected_percent)
    previous_state = build_manual_promo_state(
        authorized=state.authorized,
        authorized_percent=state.authorized_percent,
    )
    revert_percent = previous_state.authorized_percent if previous_state.authorized else Decimal("0.00")

    if normalized_selected <= Decimal("0.00"):
        return ManualPromoDecision(
            action="clear",
            selected_percent=normalized_selected,
            previous_state=previous_state,
            revert_percent=revert_percent,
        )

    if previous_state.authorized and normalized_selected == previous_state.authorized_percent:
        return ManualPromoDecision(
            action="keep",
            selected_percent=normalized_selected,
            previous_state=previous_state,
            revert_percent=revert_percent,
        )

    return ManualPromoDecision(
        action="authorize",
        selected_percent=normalized_selected,
        previous_state=previous_state,
        revert_percent=revert_percent,
    )


def apply_manual_promo_authorization(
    selected_percent: Decimal | str | int | float,
) -> ManualPromoState:
    normalized_selected = normalize_discount_value(selected_percent)
    if normalized_selected <= Decimal("0.00"):
        return clear_manual_promo_state()
    return ManualPromoState(
        authorized=True,
        authorized_percent=normalized_selected,
    )
