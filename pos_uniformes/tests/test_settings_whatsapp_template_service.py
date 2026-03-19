from __future__ import annotations

from types import SimpleNamespace
import unittest

from pos_uniformes.services.settings_whatsapp_template_service import (
    build_default_settings_whatsapp_templates,
    build_settings_whatsapp_template_map,
    render_settings_whatsapp_template,
    resolve_settings_whatsapp_templates,
)


class SettingsWhatsappTemplateServiceTests(unittest.TestCase):
    def test_build_default_settings_whatsapp_templates(self) -> None:
        defaults = build_default_settings_whatsapp_templates()
        self.assertIn("layaway_reminder", defaults)
        self.assertIn("{cliente}", defaults["client_followup"])

    def test_build_settings_whatsapp_template_map_and_render(self) -> None:
        template_map = build_settings_whatsapp_template_map(
            layaway_reminder=" Hola {cliente} ",
            layaway_liquidated=" Listo {folio} ",
            client_promotion=" Promo ",
            client_followup=" Seguimiento ",
            client_greeting=" Saludo ",
        )
        self.assertEqual(template_map["layaway_reminder"], "Hola {cliente}")
        self.assertEqual(
            render_settings_whatsapp_template("Hola {cliente}", {"cliente": "Ana"}),
            "Hola Ana",
        )

    def test_resolve_settings_whatsapp_templates_uses_defaults(self) -> None:
        defaults = build_default_settings_whatsapp_templates()
        config = SimpleNamespace(
            whatsapp_apartado_recordatorio=None,
            whatsapp_apartado_liquidado="Liquidado",
            whatsapp_cliente_promocion=None,
            whatsapp_cliente_seguimiento="Seguimiento",
            whatsapp_cliente_saludo=None,
        )

        resolved = resolve_settings_whatsapp_templates(config, default_templates=defaults)

        self.assertEqual(resolved["layaway_reminder"], defaults["layaway_reminder"])
        self.assertEqual(resolved["layaway_liquidated"], "Liquidado")
        self.assertEqual(resolved["client_greeting"], defaults["client_greeting"])


if __name__ == "__main__":
    unittest.main()
