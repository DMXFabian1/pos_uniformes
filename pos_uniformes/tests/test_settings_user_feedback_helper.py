from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_user_feedback_helper import (
    SettingsUserFeedbackView,
    build_settings_user_guard_feedback,
    build_settings_user_result_feedback,
)


class SettingsUserFeedbackHelperTests(unittest.TestCase):
    def test_build_settings_user_guard_feedback(self) -> None:
        self.assertEqual(
            build_settings_user_guard_feedback("create_user", is_admin=False, has_selection=False),
            SettingsUserFeedbackView(
                title="Sin permisos",
                message="Solo ADMIN puede crear usuarios.",
            ),
        )
        self.assertEqual(
            build_settings_user_guard_feedback("toggle_user", is_admin=True, has_selection=False),
            SettingsUserFeedbackView(
                title="Sin seleccion",
                message="Selecciona un usuario en la tabla.",
            ),
        )
        self.assertIsNone(build_settings_user_guard_feedback("toggle_user", is_admin=True, has_selection=True))

    def test_build_settings_user_result_feedback(self) -> None:
        self.assertEqual(
            build_settings_user_result_feedback("create_user", username="dani"),
            SettingsUserFeedbackView(
                title="Usuario creado",
                message="Usuario 'dani' creado correctamente.",
            ),
        )
        self.assertEqual(
            build_settings_user_result_feedback("toggle_user", username="dani", status_text="activado"),
            SettingsUserFeedbackView(
                title="Estado actualizado",
                message="Usuario 'dani' activado correctamente.",
            ),
        )
        self.assertEqual(
            build_settings_user_result_feedback("change_user_role", username="dani", role_label="ADMIN"),
            SettingsUserFeedbackView(
                title="Rol actualizado",
                message="Usuario 'dani' ahora es ADMIN.",
            ),
        )


if __name__ == "__main__":
    unittest.main()
