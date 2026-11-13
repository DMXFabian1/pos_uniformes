from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_marketing_helper import (
    build_settings_marketing_summary_label,
)


class SettingsMarketingHelperTests(unittest.TestCase):
    def test_builds_marketing_summary_label(self) -> None:
        # 2026-11-12: el resumen ya no reparte por el nivel viejo («el nivel
        # viejo retíralo», Daniel); solo cuenta clientes.
        label = build_settings_marketing_summary_label([1, 2, 3, 4, 5])

        self.assertEqual(label, "Clientes registrados: 5")
        self.assertNotIn("BASICO", label)
        self.assertNotIn("LEAL", label)

    def test_builds_empty_marketing_summary_label(self) -> None:
        self.assertEqual(build_settings_marketing_summary_label([]), "Clientes registrados: 0")


if __name__ == "__main__":
    unittest.main()
