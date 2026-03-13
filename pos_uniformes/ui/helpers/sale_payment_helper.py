"""Helpers de UI para coordinar el cobro por metodo de pago."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.business_payment_settings_service import (
    BusinessPaymentSettingsSnapshot,
    load_business_payment_settings_snapshot,
)
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


def _default_business_payment_settings_snapshot() -> BusinessPaymentSettingsSnapshot:
    return BusinessPaymentSettingsSnapshot(
        business_name="POS Uniformes",
        transfer_bank="",
        transfer_beneficiary="",
        transfer_clabe="",
        transfer_instructions="",
    )


def load_sale_business_payment_settings_snapshot() -> BusinessPaymentSettingsSnapshot:
    try:
        with get_session() as session:
            return load_business_payment_settings_snapshot(session)
    except Exception:
        return _default_business_payment_settings_snapshot()


def collect_sale_payment_details(
    window: "MainWindow",
    *,
    payment_method: str,
    total: Decimal,
) -> SalePaymentDetails | None:
    if payment_method == "Efectivo":
        return build_cash_payment_dialog(window, total)

    business = load_sale_business_payment_settings_snapshot()
    if payment_method == "Transferencia":
        return build_transfer_payment_dialog(window, total, business)
    if payment_method == "Mixto":
        return build_mixed_payment_dialog(window, total, business)
    return empty_sale_payment_details()
