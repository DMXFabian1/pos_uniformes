from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.business_print_settings_service import load_business_print_settings_snapshot


class BusinessPrintSettingsServiceTests(unittest.TestCase):
    def test_loads_snapshot_from_business_settings(self) -> None:
        config = SimpleNamespace(
            nombre_negocio="Uniformes Fabian",
            telefono="5551234567",
            direccion="Centro 123",
            pie_ticket="Vuelve pronto",
            impresora_preferida="Caja 1",
            copias_ticket=2,
        )

        with patch(
            "pos_uniformes.services.business_print_settings_service.BusinessSettingsService.get_or_create",
            return_value=config,
        ):
            snapshot = load_business_print_settings_snapshot(SimpleNamespace())

        self.assertEqual(snapshot.business_name, "Uniformes Fabian")
        self.assertEqual(snapshot.business_phone, "5551234567")
        self.assertEqual(snapshot.business_address, "Centro 123")
        self.assertEqual(snapshot.ticket_footer, "Vuelve pronto")
        self.assertEqual(snapshot.preferred_printer, "Caja 1")
        self.assertEqual(snapshot.ticket_copies, 2)

    def test_applies_defaults_when_config_fields_are_empty(self) -> None:
        config = SimpleNamespace(
            nombre_negocio="",
            telefono=None,
            direccion=None,
            pie_ticket="",
            impresora_preferida=None,
            copias_ticket=0,
        )

        with patch(
            "pos_uniformes.services.business_print_settings_service.BusinessSettingsService.get_or_create",
            return_value=config,
        ):
            snapshot = load_business_print_settings_snapshot(
                SimpleNamespace(),
                default_business_name="POS Uniformes",
                default_ticket_footer="Gracias por tu preferencia.",
            )

        self.assertEqual(snapshot.business_name, "POS Uniformes")
        self.assertEqual(snapshot.business_phone, "")
        self.assertEqual(snapshot.business_address, "")
        self.assertEqual(snapshot.ticket_footer, "Gracias por tu preferencia.")
        self.assertEqual(snapshot.preferred_printer, "")
        self.assertEqual(snapshot.ticket_copies, 1)


if __name__ == "__main__":
    unittest.main()
