from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_whatsapp_preview_helper import (
    build_settings_whatsapp_preview_text,
)


class SettingsWhatsappPreviewHelperTests(unittest.TestCase):
    def test_builds_preview_from_selected_template(self) -> None:
        text = build_settings_whatsapp_preview_text(
            "client_promotion",
            {
                "client_promotion": "Hola {cliente}, promo activa para tu codigo {codigo_cliente}.",
            },
            {},
        )

        self.assertEqual(
            text,
            "Hola Ana Perez, promo activa para tu codigo CLI-000125.",
        )

    def test_falls_back_to_default_template(self) -> None:
        text = build_settings_whatsapp_preview_text(
            "layaway_reminder",
            {},
            {
                "layaway_reminder": "Folio {folio}, saldo ${saldo}, {vencimiento}.",
            },
        )

        self.assertEqual(
            text,
            "Folio APT-20260311-AB12, saldo $350.00, Vence hoy.",
        )


if __name__ == "__main__":
    unittest.main()
