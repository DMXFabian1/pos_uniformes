from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.quote_client_creation_feedback_service import build_quote_client_created_feedback


class QuoteClientCreationFeedbackServiceTests(unittest.TestCase):
    def test_builds_feedback_with_rendered_promotion_template(self) -> None:
        config = SimpleNamespace(
            whatsapp_apartado_recordatorio=None,
            whatsapp_apartado_liquidado=None,
            whatsapp_cliente_promocion="Hola {cliente}, usa tu codigo {codigo_cliente} para tu promo.",
            whatsapp_cliente_seguimiento=None,
            whatsapp_cliente_saludo=None,
        )

        with patch(
            "pos_uniformes.services.quote_client_creation_feedback_service.BusinessSettingsService.get_or_create",
            return_value=config,
        ):
            feedback = build_quote_client_created_feedback(
                object(),
                client_name="Ana",
                client_code="CLI-012",
            )

        self.assertIn("Cliente 'Ana' asignado al presupuesto.", feedback)
        self.assertIn("Codigo: CLI-012", feedback)
        self.assertIn("Hola Ana, usa tu codigo CLI-012 para tu promo.", feedback)


if __name__ == "__main__":
    unittest.main()
