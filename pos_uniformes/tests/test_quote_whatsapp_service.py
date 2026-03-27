from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.quote_whatsapp_service import build_quote_whatsapp_view


class QuoteWhatsappServiceTests(unittest.TestCase):
    def test_build_quote_whatsapp_view_formats_message_for_active_quote(self) -> None:
        quote = SimpleNamespace(
            folio="PRE-001",
            estado=SimpleNamespace(value="EMITIDO"),
            cliente_nombre="Maria Lopez",
            cliente_telefono="5551234567",
            cliente=None,
            vigencia_hasta=datetime(2026, 3, 31, 0, 0),
            total=Decimal("449.50"),
            observacion="Entregar impreso.",
            detalles=[
                SimpleNamespace(
                    descripcion_snapshot="Playera deportiva CH azul",
                    sku_snapshot="SKU-001",
                    cantidad=2,
                    precio_unitario=Decimal("149.50"),
                    subtotal_linea=Decimal("299.00"),
                ),
            ],
        )
        fake_settings = SimpleNamespace(business_name="POS Uniformes")
        fake_service = SimpleNamespace(obtener_presupuesto=lambda session, quote_id: quote)

        with patch(
            "pos_uniformes.services.quote_whatsapp_service._resolve_quote_whatsapp_dependencies",
            return_value=(fake_service, lambda session, default_ticket_footer: fake_settings),
        ):
            view = build_quote_whatsapp_view(object(), quote_id=1)

        self.assertEqual(view.phone_number, "5551234567")
        self.assertEqual(view.customer_label, "Maria Lopez")
        self.assertIn("Hola Maria Lopez, te compartimos tu presupuesto PRE-001.", view.message)
        self.assertIn("POS Uniformes", view.message)
        self.assertIn("Total estimado: $449.50", view.message)
        self.assertIn("Vigencia: 31/03/2026", view.message)
        self.assertIn("- Playera deportiva CH azul", view.message)
        self.assertIn("SKU SKU-001 | 2 x 149.50 = 299.00", view.message)
        self.assertIn("Observaciones: Entregar impreso.", view.message)
        self.assertIn("responde con tu folio PRE-001.", view.message)

    def test_build_quote_whatsapp_view_requires_phone(self) -> None:
        quote = SimpleNamespace(
            folio="PRE-001",
            cliente_nombre="Maria Lopez",
            cliente_telefono="",
            cliente=None,
        )
        fake_settings = SimpleNamespace(business_name="POS Uniformes")
        fake_service = SimpleNamespace(obtener_presupuesto=lambda session, quote_id: quote)

        with patch(
            "pos_uniformes.services.quote_whatsapp_service._resolve_quote_whatsapp_dependencies",
            return_value=(fake_service, lambda session, default_ticket_footer: fake_settings),
        ):
            with self.assertRaisesRegex(ValueError, "no tiene telefono"):
                build_quote_whatsapp_view(object(), quote_id=1)


if __name__ == "__main__":
    unittest.main()
