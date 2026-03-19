"""Mensajes visibles para el cierre de venta en Caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SaleCheckoutFeedbackView:
    title: str
    message: str
    tone: str
    auto_clear_ms: int


def build_sale_checkout_error_message(error_message: str) -> str:
    if "Stock insuficiente" in error_message:
        return "Uno de los productos ya no tiene stock suficiente. Revisa el carrito y vuelve a intentar."
    return error_message


def build_sale_checkout_success_feedback(
    *,
    folio: str,
    total: Decimal,
    payment_method: str,
) -> SaleCheckoutFeedbackView:
    return SaleCheckoutFeedbackView(
        title="Venta registrada",
        message=f"Venta {folio} registrada. Total cobrado: {total} via {payment_method}.",
        tone="positive",
        auto_clear_ms=2200,
    )
