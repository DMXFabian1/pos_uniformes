"""Feedback visible posterior a acciones de venta en Caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.ui.helpers.recent_sale_feedback_helper import build_recent_sale_result_feedback
from pos_uniformes.ui.helpers.sale_checkout_feedback_helper import build_sale_checkout_success_feedback


@dataclass(frozen=True)
class SalePostActionView:
    feedback_message: str
    feedback_tone: str
    feedback_auto_clear_ms: int | None
    refresh_all: bool
    clear_sale_cart: bool
    reset_sale_form: bool
    focus_sale_input: bool
    play_feedback_sound: bool
    notice_title: str | None = None
    notice_message: str | None = None


def build_sale_checkout_post_action_view(
    *,
    folio: str,
    total: Decimal,
    payment_method: str,
    loyalty_transition_notice: str,
) -> SalePostActionView:
    feedback = build_sale_checkout_success_feedback(
        folio=folio,
        total=total,
        payment_method=payment_method,
    )
    notice_message = loyalty_transition_notice.strip()
    return SalePostActionView(
        feedback_message=feedback.message,
        feedback_tone=feedback.tone,
        feedback_auto_clear_ms=feedback.auto_clear_ms,
        refresh_all=True,
        clear_sale_cart=True,
        reset_sale_form=True,
        focus_sale_input=True,
        play_feedback_sound=True,
        notice_title="Nivel actualizado para siguiente compra" if notice_message else None,
        notice_message=notice_message or None,
    )


def build_sale_cancel_post_action_view() -> SalePostActionView:
    feedback = build_recent_sale_result_feedback("cancel_sale")
    return SalePostActionView(
        feedback_message=feedback.message,
        feedback_tone="warning",
        feedback_auto_clear_ms=1800,
        refresh_all=True,
        clear_sale_cart=False,
        reset_sale_form=False,
        focus_sale_input=False,
        play_feedback_sound=False,
    )
