"""Normalizacion y estado operativo para captura de abonos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


VALID_LAYAWAY_PAYMENT_METHODS = {"Efectivo", "Transferencia", "Mixto"}


@dataclass(frozen=True)
class LayawayPaymentState:
    payment_method: str
    cash_amount: Decimal
    cash_enabled: bool
    cash_maximum: Decimal


@dataclass(frozen=True)
class LayawayPaymentInput:
    amount: Decimal
    payment_method: str
    cash_amount: Decimal
    reference: str
    notes: str


def normalize_layaway_payment_method(payment_method: str) -> str:
    normalized_method = payment_method.strip() or "Efectivo"
    if normalized_method not in VALID_LAYAWAY_PAYMENT_METHODS:
        return "Efectivo"
    return normalized_method


def resolve_layaway_payment_state(
    *,
    payment_method: str,
    amount: Decimal | str | int | float,
    current_cash_amount: Decimal | str | int | float = Decimal("0.00"),
) -> LayawayPaymentState:
    normalized_amount = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    normalized_cash_amount = Decimal(str(current_cash_amount or 0)).quantize(Decimal("0.01"))
    normalized_method = normalize_layaway_payment_method(payment_method)

    if normalized_method == "Efectivo":
        return LayawayPaymentState(
            payment_method=normalized_method,
            cash_amount=normalized_amount,
            cash_enabled=False,
            cash_maximum=normalized_amount,
        )
    if normalized_method == "Transferencia":
        return LayawayPaymentState(
            payment_method=normalized_method,
            cash_amount=Decimal("0.00"),
            cash_enabled=False,
            cash_maximum=normalized_amount,
        )

    clamped_cash_amount = normalized_cash_amount
    if clamped_cash_amount < Decimal("0.00"):
        clamped_cash_amount = Decimal("0.00")
    if clamped_cash_amount > normalized_amount:
        clamped_cash_amount = normalized_amount
    return LayawayPaymentState(
        payment_method=normalized_method,
        cash_amount=clamped_cash_amount,
        cash_enabled=True,
        cash_maximum=normalized_amount,
    )


def build_layaway_payment_input(
    *,
    amount: Decimal | str | int | float,
    payment_method: str,
    cash_amount: Decimal | str | int | float,
    reference: str = "",
    notes: str = "",
) -> LayawayPaymentInput:
    normalized_amount = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    state = resolve_layaway_payment_state(
        payment_method=payment_method,
        amount=normalized_amount,
        current_cash_amount=cash_amount,
    )
    return LayawayPaymentInput(
        amount=normalized_amount,
        payment_method=state.payment_method,
        cash_amount=state.cash_amount,
        reference=reference.strip(),
        notes=notes.strip(),
    )
