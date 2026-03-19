from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_marketing_helper import (
    build_settings_marketing_summary_label,
)


class SettingsMarketingHelperTests(unittest.TestCase):
    def test_builds_marketing_summary_label(self) -> None:
        label = build_settings_marketing_summary_label(
            [
                "BASICO",
                "LEAL",
                "LEAL",
                "PROFESOR",
                "MAYORISTA",
            ]
        )

        self.assertEqual(
            label,
            (
                "Clientes registrados: 5\n"
                "BASICO: 1 | LEAL: 2 | PROFESOR: 1 | MAYORISTA: 1"
            ),
        )

    def test_builds_empty_marketing_summary_label(self) -> None:
        label = build_settings_marketing_summary_label([])

        self.assertEqual(
            label,
            (
                "Clientes registrados: 0\n"
                "BASICO: 0 | LEAL: 0 | PROFESOR: 0 | MAYORISTA: 0"
            ),
        )


if __name__ == "__main__":
    unittest.main()
