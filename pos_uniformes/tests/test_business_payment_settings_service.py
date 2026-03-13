from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.business_payment_settings_service import load_business_payment_settings_snapshot


class BusinessPaymentSettingsServiceTests(unittest.TestCase):
    def test_loads_snapshot_from_business_settings(self) -> None:
        config = SimpleNamespace(
            nombre_negocio="Uniformes Fabian",
            transferencia_banco="BBVA",
            transferencia_beneficiario="Daniel Fabian",
            transferencia_clabe="0123456789",
            transferencia_instrucciones="Enviar comprobante",
        )

        with patch(
            "pos_uniformes.services.business_payment_settings_service.BusinessSettingsService.get_or_create",
            return_value=config,
        ):
            snapshot = load_business_payment_settings_snapshot(SimpleNamespace())

        self.assertEqual(snapshot.business_name, "Uniformes Fabian")
        self.assertEqual(snapshot.transfer_bank, "BBVA")
        self.assertEqual(snapshot.transfer_beneficiary, "Daniel Fabian")
        self.assertEqual(snapshot.transfer_clabe, "0123456789")
        self.assertEqual(snapshot.transfer_instructions, "Enviar comprobante")

    def test_applies_defaults_when_config_fields_are_empty(self) -> None:
        config = SimpleNamespace(
            nombre_negocio="",
            transferencia_banco=None,
            transferencia_beneficiario=None,
            transferencia_clabe=None,
            transferencia_instrucciones=None,
        )

        with patch(
            "pos_uniformes.services.business_payment_settings_service.BusinessSettingsService.get_or_create",
            return_value=config,
        ):
            snapshot = load_business_payment_settings_snapshot(SimpleNamespace())

        self.assertEqual(snapshot.business_name, "POS Uniformes")
        self.assertEqual(snapshot.transfer_bank, "")
        self.assertEqual(snapshot.transfer_beneficiary, "")
        self.assertEqual(snapshot.transfer_clabe, "")
        self.assertEqual(snapshot.transfer_instructions, "")


if __name__ == "__main__":
    unittest.main()
