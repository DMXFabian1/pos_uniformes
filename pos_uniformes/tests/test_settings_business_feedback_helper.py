from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_business_feedback_helper import (
    SettingsBusinessFeedbackView,
    build_settings_business_guard_feedback,
    build_settings_business_result_feedback,
)


class SettingsBusinessFeedbackHelperTests(unittest.TestCase):
    def test_build_settings_business_guard_feedback(self) -> None:
        self.assertIsNone(build_settings_business_guard_feedback(is_admin=True))
        self.assertEqual(
            build_settings_business_guard_feedback(is_admin=False),
            SettingsBusinessFeedbackView(
                title="Sin permisos",
                message="Solo ADMIN puede actualizar esta configuracion.",
            ),
        )

    def test_build_settings_business_result_feedback(self) -> None:
        self.assertEqual(
            build_settings_business_result_feedback("Actualizado"),
            SettingsBusinessFeedbackView(
                title="Configuracion guardada",
                message="Actualizado",
            ),
        )


if __name__ == "__main__":
    unittest.main()
