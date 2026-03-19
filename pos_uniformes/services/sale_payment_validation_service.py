"""Reglas puras de validacion para cobros en Caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CashPaymentValidation:
    received: Decimal
    change: Decimal
    is_sufficient: bool
    status_message: str
    status_tone: str


@dataclass(frozen=True)
class MixedPaymentValidation:
    transfer_amount: Decimal
    cash_received: Decimal
    cash_due: Decimal
    change: Decimal
    is_sufficient: bool
    error_message: str | None


def validate_cash_payment(*, total: Decimal, received: Decimal | str | int | float) -> CashPaymentValidation:
    normalized_total = Decimal(str(total or 0)).quantize(Decimal("0.01"))
    normalized_received = Decimal(str(received or 0)).quantize(Decimal("0.01"))
    change = normalized_received - normalized_total
    if change < Decimal("0.00"):
        return CashPaymentValidation(
            received=normalized_received,
            change=Decimal("0.00"),
            is_sufficient=False,
            status_message="Falta efectivo para cubrir el total.",
            status_tone="warning",
        )
    return CashPaymentValidation(
        received=normalized_received,
        change=change.quantize(Decimal("0.01")),
        is_sufficient=True,
        status_message="Monto suficiente para cobrar.",
        status_tone="positive",
    )


def validate_transfer_payment_availability(business) -> str | None:
    if getattr(business, "transfer_clabe", "") or getattr(business, "transfer_instructions", ""):
        return None
    return "Configura CLABE o instrucciones de transferencia en Configuracion > Negocio e impresion."


def validate_mixed_payment(
    *,
    total: Decimal,
    transfer_amount: Decimal | str | int | float,
    cash_received: Decimal | str | int | float,
) -> MixedPaymentValidation:
    normalized_total = Decimal(str(total or 0)).quantize(Decimal("0.01"))
    normalized_transfer = Decimal(str(transfer_amount or 0)).quantize(Decimal("0.01"))
    normalized_cash = Decimal(str(cash_received or 0)).quantize(Decimal("0.01"))
    cash_due = normalized_total - normalized_transfer
    if cash_due < Decimal("0.00"):
        cash_due = Decimal("0.00")
    change = normalized_cash - cash_due
    if change < Decimal("0.00"):
        change = Decimal("0.00")
    if normalized_transfer + normalized_cash < normalized_total:
        return MixedPaymentValidation(
            transfer_amount=normalized_transfer,
            cash_received=normalized_cash,
            cash_due=cash_due.quantize(Decimal("0.01")),
            change=change.quantize(Decimal("0.01")),
            is_sufficient=False,
            error_message="La suma de transferencia y efectivo debe cubrir el total.",
        )
    return MixedPaymentValidation(
        transfer_amount=normalized_transfer,
        cash_received=normalized_cash,
        cash_due=cash_due.quantize(Decimal("0.01")),
        change=change.quantize(Decimal("0.01")),
        is_sufficient=True,
        error_message=None,
    )
