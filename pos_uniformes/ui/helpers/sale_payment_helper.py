"""Helpers de UI para coordinar el cobro por metodo de pago."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pos_uniformes.services.sale_payment_collection_service import build_sale_payment_dialog_request
from pos_uniformes.services.sale_payment_note_service import (
    SalePaymentDetails,
    empty_sale_payment_details,
)
from pos_uniformes.ui.dialogs.payment_dialogs import (
    build_cash_payment_dialog,
    build_mixed_payment_dialog,
    build_transfer_payment_dialog,
)

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


def collect_sale_payment_details(
    window: "MainWindow",
    *,
    payment_method: str,
    total: Decimal,
) -> SalePaymentDetails | None:
    request = build_sale_payment_dialog_request(payment_method)
    if request.dialog_key == "cash":
        return build_cash_payment_dialog(window, total)
    if request.dialog_key == "transfer" and request.business is not None:
        return build_transfer_payment_dialog(window, total, request.business)
    if request.dialog_key == "mixed" and request.business is not None:
        return build_mixed_payment_dialog(window, total, request.business)
    return empty_sale_payment_details()
