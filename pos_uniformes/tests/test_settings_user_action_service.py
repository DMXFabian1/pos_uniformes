from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.settings_user_action_service import (
    SettingsUserActionResult,
    SettingsUserPromptSnapshot,
    change_settings_user_password,
    change_settings_user_role,
    create_settings_user,
    load_settings_user_prompt_snapshot,
    toggle_settings_user,
    update_settings_user,
)


class SettingsUserActionServiceTests(unittest.TestCase):
    def test_load_settings_user_prompt_snapshot(self) -> None:
        user = SimpleNamespace(username="admin", nombre_completo="Admin Uno", rol="ADMIN")
        session = SimpleNamespace(get=lambda model, item_id: user if item_id == 7 else None)

        with patch(
            "pos_uniformes.services.settings_user_action_service._resolve_settings_user_model",
            return_value=object(),
        ):
            snapshot = load_settings_user_prompt_snapshot(session, user_id=7)

        self.assertEqual(
            snapshot,
            SettingsUserPromptSnapshot(
                username="admin",
                full_name="Admin Uno",
                current_role="ADMIN",
            ),
        )

    def test_create_settings_user(self) -> None:
        admin_user = object()
        created_user = SimpleNamespace(username="nuevo")
        session = SimpleNamespace(get=lambda model, item_id: admin_user if item_id == 1 else None)
        fake_service = SimpleNamespace(create_user=lambda **kwargs: created_user)

        with patch(
            "pos_uniformes.services.settings_user_action_service._resolve_settings_user_action_dependencies",
            return_value=(fake_service, object()),
        ):
            result = create_settings_user(
                session,
                admin_user_id=1,
                payload={
                    "username": "nuevo",
                    "nombre_completo": "Nuevo Usuario",
                    "rol": "ADMIN",
                    "password": "secreta",
                },
            )

        self.assertEqual(result, SettingsUserActionResult(username="nuevo"))

    def test_toggle_change_password_and_update(self) -> None:
        admin_user = SimpleNamespace(id=1)
        target_user = SimpleNamespace(username="dani", activo=False)
        session = SimpleNamespace(get=lambda model, item_id: admin_user if item_id == 1 else target_user if item_id == 7 else None)
        fake_service = SimpleNamespace(
            toggle_active=lambda _session, _admin, _target: target_user,
            change_role=lambda _session, _admin, _target, new_role: SimpleNamespace(username="dani", rol=new_role),
            change_password=lambda _session, _admin, _target, new_password: target_user,
            update_user=lambda **kwargs: target_user,
        )
        fake_role = SimpleNamespace(value="CAJERO")

        with patch(
            "pos_uniformes.services.settings_user_action_service._resolve_settings_user_action_dependencies",
            return_value=(fake_service, object()),
        ):
            toggle_result = toggle_settings_user(session, admin_user_id=1, user_id=7)
            role_result = change_settings_user_role(session, admin_user_id=1, user_id=7, new_role=fake_role)
            password_result = change_settings_user_password(
                session,
                admin_user_id=1,
                user_id=7,
                new_password="nueva",
            )
            update_result = update_settings_user(
                session,
                admin_user_id=1,
                user_id=7,
                payload={
                    "username": "dani",
                    "nombre_completo": "Daniel",
                    "rol": fake_role,
                },
            )

        self.assertEqual(
            toggle_result,
            SettingsUserActionResult(username="dani", status_text="desactivado"),
        )
        self.assertEqual(
            role_result,
            SettingsUserActionResult(username="dani", role_label="CAJERO"),
        )
        self.assertEqual(password_result, SettingsUserActionResult(username="dani"))
        self.assertEqual(update_result, SettingsUserActionResult(username="dani"))


if __name__ == "__main__":
    unittest.main()
