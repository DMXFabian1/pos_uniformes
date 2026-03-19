"""Contexto operativo de descuentos y promo manual en Caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from pos_uniformes.services.manual_promo_flow_service import (
    build_manual_promo_state,
    clear_manual_promo_state,
    current_manual_promo_percent,
    decide_manual_promo_change,
    resolve_manual_promo_transition,
)
from pos_uniformes.services.sale_discount_service import (
    build_sale_discount_breakdown,
    calculate_sale_pricing,
    calculate_sale_totals,
    effective_sale_discount_percent,
)
from pos_uniformes.ui.helpers.sale_client_selection_helper import (
    build_sale_client_selection_ui_state,
)


@dataclass(frozen=True)
class SaleDiscountContext:
    loyalty_discount: Decimal
    promo_discount: Decimal
    effective_discount: Decimal
    breakdown: dict[str, object]


def load_sale_discount_presets(
    session,
    *,
    normalize_discount_value: Callable[[object | None], Decimal],
) -> list[Decimal]:
    default_values = [
        Decimal("5.00"),
        Decimal("10.00"),
        Decimal("15.00"),
        Decimal("20.00"),
    ]
    business_settings_service = _resolve_sale_discount_preset_dependencies()
    try:
        config = business_settings_service.get_or_create(session)
        values = [
            normalize_discount_value(config.discount_basico),
            normalize_discount_value(config.discount_leal),
            normalize_discount_value(config.discount_profesor),
            normalize_discount_value(config.discount_mayorista),
        ]
    except Exception:
        values = default_values
    return sorted({value for value in values if value > Decimal("0.00")})


def clear_sale_manual_promo_snapshot():
    return clear_manual_promo_state()


def build_sale_manual_promo_snapshot(*, authorized: bool, authorized_percent: Decimal):
    return build_manual_promo_state(
        authorized=authorized,
        authorized_percent=authorized_percent,
    )


def resolve_sale_client_discount_ui_state(
    session,
    *,
    selected_client_id: int | str | None,
    reset_manual: bool,
    normalize_discount_value: Callable[[object | None], Decimal],
    format_discount_label: Callable[[Decimal | str | int | float], str],
):
    selected_client_service = _resolve_sale_client_discount_ui_dependencies()
    try:
        sync_state = selected_client_service.resolve_sale_selected_client_sync_state(
            session,
            selected_client_id=selected_client_id,
            normalize_discount_value=normalize_discount_value,
        )
    except Exception:
        sync_state = selected_client_service.resolve_sale_selected_client_sync_state(
            None,
            selected_client_id=None,
            normalize_discount_value=normalize_discount_value,
        )
    return build_sale_client_selection_ui_state(
        sync_state=sync_state,
        reset_manual=reset_manual,
        normalize_discount_value=normalize_discount_value,
        format_discount_label=format_discount_label,
    )


def resolve_sale_manual_discount_transition(
    *,
    selected_percent: object,
    authorized: bool,
    authorized_percent: Decimal,
    format_discount_label: Callable[[Decimal | str | int | float], str],
    authorize_manual_promo: Callable[[Decimal], bool],
):
    decision = decide_manual_promo_change(
        selected_percent=selected_percent,
        state=build_sale_manual_promo_snapshot(
            authorized=authorized,
            authorized_percent=authorized_percent,
        ),
    )
    authorization_granted = (
        authorize_manual_promo(decision.selected_percent)
        if decision.action == "authorize"
        else False
    )
    return resolve_manual_promo_transition(
        decision=decision,
        authorization_granted=authorization_granted,
        format_discount_label=format_discount_label,
    )


def verify_sale_manual_promo_code(session, code: str) -> None:
    manual_promo_service = _resolve_sale_manual_promo_dependencies()
    if not manual_promo_service.verify_authorization_code(session, code):
        raise ValueError("Codigo invalido.")


def build_sale_discount_context(
    *,
    locked_to_client: bool,
    locked_discount_percent: Decimal,
    locked_source_label: str,
    selected_discount_percent: object,
    manual_promo_authorized: bool,
    manual_promo_authorized_percent: Decimal,
) -> SaleDiscountContext:
    loyalty_discount = locked_discount_percent if locked_to_client else Decimal("0.00")
    promo_discount = current_manual_promo_percent(
        selected_percent=selected_discount_percent,
        state=build_sale_manual_promo_snapshot(
            authorized=manual_promo_authorized,
            authorized_percent=manual_promo_authorized_percent,
        ),
    )
    return SaleDiscountContext(
        loyalty_discount=loyalty_discount,
        promo_discount=promo_discount,
        effective_discount=effective_sale_discount_percent(
            loyalty_discount=loyalty_discount,
            promo_discount=promo_discount,
        ),
        breakdown=build_sale_discount_breakdown(
            loyalty_discount=loyalty_discount,
            promo_discount=promo_discount,
            loyalty_source=locked_source_label or "Cliente",
        ),
    )


def calculate_sale_discount_totals(
    sale_cart,
    *,
    locked_to_client: bool,
    locked_discount_percent: Decimal,
    selected_discount_percent: object,
    manual_promo_authorized: bool,
    manual_promo_authorized_percent: Decimal,
):
    context = build_sale_discount_context(
        locked_to_client=locked_to_client,
        locked_discount_percent=locked_discount_percent,
        locked_source_label="",
        selected_discount_percent=selected_discount_percent,
        manual_promo_authorized=manual_promo_authorized,
        manual_promo_authorized_percent=manual_promo_authorized_percent,
    )
    return calculate_sale_totals(
        sale_cart,
        loyalty_discount=context.loyalty_discount,
        promo_discount=context.promo_discount,
    )


def calculate_sale_discount_pricing(
    sale_cart,
    *,
    locked_to_client: bool,
    locked_discount_percent: Decimal,
    selected_discount_percent: object,
    manual_promo_authorized: bool,
    manual_promo_authorized_percent: Decimal,
):
    context = build_sale_discount_context(
        locked_to_client=locked_to_client,
        locked_discount_percent=locked_discount_percent,
        locked_source_label="",
        selected_discount_percent=selected_discount_percent,
        manual_promo_authorized=manual_promo_authorized,
        manual_promo_authorized_percent=manual_promo_authorized_percent,
    )
    return calculate_sale_pricing(
        sale_cart,
        loyalty_discount=context.loyalty_discount,
        promo_discount=context.promo_discount,
    )


def _resolve_sale_discount_preset_dependencies():
    from pos_uniformes.services.business_settings_service import BusinessSettingsService

    return BusinessSettingsService


def _resolve_sale_client_discount_ui_dependencies():
    from pos_uniformes.services import sale_selected_client_service

    return sale_selected_client_service


def _resolve_sale_manual_promo_dependencies():
    from pos_uniformes.services.manual_promo_service import ManualPromoService

    return ManualPromoService
