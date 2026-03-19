from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.settings_business_action_service import (
    SettingsBusinessFormSnapshot,
    load_settings_business_form_snapshot,
    save_settings_business_payload,
)


class SettingsBusinessActionServiceTests(unittest.TestCase):
    def test_load_settings_business_form_snapshot(self) -> None:
        config = SimpleNamespace(
            nombre_negocio="POS Uniformes",
            logo_path="logo.png",
            loyalty_review_window_days=365,
            leal_spend_threshold=3000,
            leal_purchase_count_threshold=3,
            leal_purchase_sum_threshold=2000,
            discount_basico=5,
            discount_leal=10,
            discount_profesor=15,
            discount_mayorista=20,
            telefono="555",
            direccion="Centro",
            pie_ticket="Gracias",
            transferencia_banco="Banco",
            transferencia_beneficiario="Benef",
            transferencia_clabe="123",
            transferencia_instrucciones="Trae comprobante",
            impresora_preferida="Brother",
            copias_ticket=2,
        )
        fake_business_service = SimpleNamespace(get_or_create=lambda session: config)
        fake_whatsapp_service = SimpleNamespace(
            resolve_settings_whatsapp_templates=lambda cfg, default_templates: {
                "layaway_reminder": "Recordatorio",
                "layaway_liquidated": "Liquidado",
                "client_promotion": "Promo",
                "client_followup": "Seguimiento",
                "client_greeting": "Saludo",
            }
        )

        with patch(
            "pos_uniformes.services.settings_business_action_service._resolve_settings_business_form_dependencies",
            return_value=(fake_business_service, fake_whatsapp_service),
        ):
            snapshot = load_settings_business_form_snapshot(
                object(),
                default_templates={"layaway_reminder": "x"},
            )

        self.assertEqual(
            snapshot,
            SettingsBusinessFormSnapshot(
                business_name="POS Uniformes",
                logo_path="logo.png",
                loyalty_review_window_days=365,
                leal_spend_threshold=3000.0,
                leal_purchase_count_threshold=3,
                leal_purchase_sum_threshold=2000.0,
                discount_basico=5.0,
                discount_leal=10.0,
                discount_profesor=15.0,
                discount_mayorista=20.0,
                phone="555",
                address="Centro",
                footer="Gracias",
                transfer_bank="Banco",
                transfer_beneficiary="Benef",
                transfer_clabe="123",
                transfer_instructions="Trae comprobante",
                whatsapp_layaway_reminder="Recordatorio",
                whatsapp_layaway_liquidated="Liquidado",
                whatsapp_client_promotion="Promo",
                whatsapp_client_followup="Seguimiento",
                whatsapp_client_greeting="Saludo",
                preferred_printer="Brother",
                ticket_copies=2,
            ),
        )

    def test_save_settings_business_payload(self) -> None:
        admin_user = object()
        session = SimpleNamespace(get=lambda model, item_id: admin_user if item_id == 7 else None)
        fake_business_service = SimpleNamespace(update_settings=lambda **kwargs: None)

        with patch(
            "pos_uniformes.services.settings_business_action_service._resolve_settings_business_action_dependencies",
            return_value=(fake_business_service, object()),
        ):
            save_settings_business_payload(
                session,
                admin_user_id=7,
                payload=SimpleNamespace(nombre_negocio="POS"),
            )


if __name__ == "__main__":
    unittest.main()
