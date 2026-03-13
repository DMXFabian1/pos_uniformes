"""Helpers para cargar configuracion operativa de cobro y transferencia."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.services.business_settings_service import BusinessSettingsService


@dataclass(frozen=True)
class BusinessPaymentSettingsSnapshot:
    business_name: str
    transfer_bank: str
    transfer_beneficiary: str
    transfer_clabe: str
    transfer_instructions: str


def load_business_payment_settings_snapshot(
    session,
    *,
    default_business_name: str = "POS Uniformes",
) -> BusinessPaymentSettingsSnapshot:
    config = BusinessSettingsService.get_or_create(session)
    return BusinessPaymentSettingsSnapshot(
        business_name=config.nombre_negocio or default_business_name,
        transfer_bank=config.transferencia_banco or "",
        transfer_beneficiary=config.transferencia_beneficiario or "",
        transfer_clabe=config.transferencia_clabe or "",
        transfer_instructions=config.transferencia_instrucciones or "",
    )
