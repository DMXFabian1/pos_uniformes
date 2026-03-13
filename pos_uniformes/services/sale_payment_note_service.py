"""Detalles puros de cobro para notas operativas de venta."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SalePaymentDetails:
    note_lines: tuple[str, ...] = ()


def empty_sale_payment_details() -> SalePaymentDetails:
    return SalePaymentDetails()


def build_cash_payment_details(
    *,
    received: Decimal | str | int | float,
    change: Decimal | str | int | float,
    reference: str = "",
) -> SalePaymentDetails:
    return SalePaymentDetails(
        note_lines=(
            f"Recibido: {Decimal(str(received or 0)).quantize(Decimal('0.01'))}",
            f"Cambio: {Decimal(str(change or 0)).quantize(Decimal('0.01'))}",
            f"Referencia: {reference.strip() or 'Sin referencia'}",
        )
    )


def build_transfer_payment_details(reference: str = "") -> SalePaymentDetails:
    return SalePaymentDetails(
        note_lines=(
            f"Referencia transferencia: {reference.strip() or 'Sin referencia'}",
        )
    )


def build_mixed_payment_details(
    *,
    transfer_amount: Decimal | str | int | float,
    cash_received: Decimal | str | int | float,
    change: Decimal | str | int | float,
    reference: str = "",
) -> SalePaymentDetails:
    return SalePaymentDetails(
        note_lines=(
            f"Transferencia: {Decimal(str(transfer_amount or 0)).quantize(Decimal('0.01'))}",
            f"Efectivo recibido: {Decimal(str(cash_received or 0)).quantize(Decimal('0.01'))}",
            f"Cambio: {Decimal(str(change or 0)).quantize(Decimal('0.01'))}",
            f"Referencia transferencia: {reference.strip() or 'Sin referencia'}",
        )
    )
