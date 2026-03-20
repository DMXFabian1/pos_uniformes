from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.quote_whatsapp_service import QuoteWhatsappView, build_quote_whatsapp_view


class QuoteWhatsappServiceTests(unittest.TestCase):
    def test_build_quote_whatsapp_view(self) -> None:
        quote = SimpleNamespace(
            folio="PRE-001",
            estado=SimpleNamespace(value="EMITIDO"),
            cliente_nombre="Maria Lopez",
            cliente_telefono="5551234567",
            cliente=None,
            vigencia_hasta=datetime(2026, 3, 31, 0, 0),
            total=Decimal("449.50"),
            observacion="Entregar en mostrador.",
            detalles=[
                SimpleNamespace(
                    descripcion_snapshot="Playera deportiva CH azul",
                    cantidad=2,
                    subtotal_linea=Decimal("299.00"),
                )
            ],
        )
        fake_service = SimpleNamespace(obtener_presupuesto=lambda session, quote_id: quote)
        fake_settings_loader = lambda session, default_ticket_footer="": SimpleNamespace(business_name="POS Uniformes")

        with patch(
            "pos_uniformes.services.quote_whatsapp_service._resolve_quote_whatsapp_dependencies",
            return_value=(fake_service, fake_settings_loader),
        ):
            view = build_quote_whatsapp_view(SimpleNamespace(), quote_id=10)

        self.assertIsInstance(view, QuoteWhatsappView)
        self.assertEqual(view.phone_number, "5551234567")
        self.assertEqual(view.customer_label, "Maria Lopez")
        self.assertIn("presupuesto PRE-001", view.message)
        self.assertIn("Total estimado: $449.50", view.message)
        self.assertIn("Vigencia: 2026-03-31", view.message)


if __name__ == "__main__":
    unittest.main()
