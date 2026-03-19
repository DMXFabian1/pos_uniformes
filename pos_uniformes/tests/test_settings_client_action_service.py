from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.settings_client_action_service import (
    SettingsClientActionResult,
    SettingsClientPromptSnapshot,
    create_settings_client,
    generate_settings_client_qr,
    load_settings_client_prompt_snapshot,
    toggle_settings_client,
    update_settings_client,
)


class SettingsClientActionServiceTests(unittest.TestCase):
    def test_load_settings_client_prompt_snapshot(self) -> None:
        client = SimpleNamespace(
            nombre="Ana",
            tipo_cliente=SimpleNamespace(value="GENERAL"),
            descuento_preferente="10",
            telefono="555",
            notas="VIP",
        )
        session = SimpleNamespace(get=lambda model, item_id: client if item_id == 3 else None)

        with patch(
            "pos_uniformes.services.settings_client_action_service._resolve_settings_client_model",
            return_value=object(),
        ):
            snapshot = load_settings_client_prompt_snapshot(session, client_id=3)

        self.assertEqual(
            snapshot,
            SettingsClientPromptSnapshot("Ana", "GENERAL", "10.00", "555", "VIP"),
        )

    def test_client_mutations_and_qr(self) -> None:
        admin_user = object()
        fake_role = lambda value: value
        client = SimpleNamespace(nombre="Ana", codigo_cliente="CLI-001", activo=False)
        session = SimpleNamespace(get=lambda model, item_id: admin_user if item_id == 1 else client if item_id == 3 else None, flush=lambda: None)
        fake_service = SimpleNamespace(
            create_client=lambda **kwargs: client,
            update_client=lambda **kwargs: client,
            toggle_active=lambda _session, _admin, _client: client,
        )
        fake_qr = SimpleNamespace(generate_for_client=lambda _client: Path("/tmp/qr.png"))

        with patch(
            "pos_uniformes.services.settings_client_action_service._resolve_settings_client_create_dependencies",
            return_value=(fake_service, object(), fake_role),
        ), patch(
            "pos_uniformes.services.settings_client_action_service._resolve_settings_client_update_dependencies",
            return_value=(fake_service, object(), object(), fake_role),
        ), patch(
            "pos_uniformes.services.settings_client_action_service._resolve_settings_client_toggle_dependencies",
            return_value=(fake_service, object(), object()),
        ), patch(
            "pos_uniformes.services.settings_client_action_service._resolve_settings_client_qr_dependencies",
            return_value=(object(), fake_qr),
        ):
            create_result = create_settings_client(
                session,
                admin_user_id=1,
                payload={
                    "nombre": "Ana",
                    "tipo_cliente": "GENERAL",
                    "descuento_preferente": "10",
                    "telefono": "555",
                    "notas": "VIP",
                },
                render_card=lambda _client: (Path("/tmp/card.png"), None),
            )
            update_result = update_settings_client(
                session,
                admin_user_id=1,
                client_id=3,
                payload={
                    "nombre": "Ana",
                    "tipo_cliente": "GENERAL",
                    "descuento_preferente": "10",
                    "telefono": "555",
                    "notas": "VIP",
                },
                render_card=lambda _client: (None, "pendiente"),
            )
            toggle_result = toggle_settings_client(session, admin_user_id=1, client_id=3)
            qr_result = generate_settings_client_qr(session, client_id=3)

        self.assertEqual(
            create_result,
            SettingsClientActionResult("Ana", "CLI-001", None, Path("/tmp/card.png"), None),
        )
        self.assertEqual(
            update_result,
            SettingsClientActionResult("Ana", "CLI-001", None, None, "pendiente"),
        )
        self.assertEqual(
            toggle_result,
            SettingsClientActionResult("Ana", "CLI-001", "desactivado", None, None),
        )
        self.assertEqual(
            qr_result,
            SettingsClientActionResult("Ana", "CLI-001", None, Path("/tmp/qr.png"), None),
        )


if __name__ == "__main__":
    unittest.main()
