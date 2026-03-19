"""Orquestacion de captura de cobro por metodo de pago."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SalePaymentBusinessSnapshot:
    business_name: str
    transfer_bank: str
    transfer_beneficiary: str
    transfer_clabe: str
    transfer_instructions: str


@dataclass(frozen=True)
class SalePaymentDialogRequest:
    dialog_key: str
    business: SalePaymentBusinessSnapshot | None = None


def build_sale_payment_dialog_request(payment_method: str) -> SalePaymentDialogRequest:
    normalized = (payment_method or "").strip() or "Efectivo"
    if normalized == "Efectivo":
        return SalePaymentDialogRequest(dialog_key="cash")
    if normalized == "Transferencia":
        return SalePaymentDialogRequest(
            dialog_key="transfer",
            business=load_sale_payment_business_snapshot(),
        )
    if normalized == "Mixto":
        return SalePaymentDialogRequest(
            dialog_key="mixed",
            business=load_sale_payment_business_snapshot(),
        )
    return SalePaymentDialogRequest(dialog_key="none")


def load_sale_payment_business_snapshot() -> SalePaymentBusinessSnapshot:
    try:
        get_session, load_snapshot = _resolve_sale_payment_collection_dependencies()
        with get_session() as session:
            snapshot = load_snapshot(session)
    except Exception:
        return _default_sale_payment_business_snapshot()
    return SalePaymentBusinessSnapshot(
        business_name=str(snapshot.business_name or "POS Uniformes"),
        transfer_bank=str(snapshot.transfer_bank or ""),
        transfer_beneficiary=str(snapshot.transfer_beneficiary or ""),
        transfer_clabe=str(snapshot.transfer_clabe or ""),
        transfer_instructions=str(snapshot.transfer_instructions or ""),
    )


def _default_sale_payment_business_snapshot() -> SalePaymentBusinessSnapshot:
    return SalePaymentBusinessSnapshot(
        business_name="POS Uniformes",
        transfer_bank="",
        transfer_beneficiary="",
        transfer_clabe="",
        transfer_instructions="",
    )


def _resolve_sale_payment_collection_dependencies():
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.business_payment_settings_service import load_business_payment_settings_snapshot

    return get_session, load_business_payment_settings_snapshot
