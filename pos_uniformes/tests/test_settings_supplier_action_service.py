from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.settings_supplier_action_service import (
    SettingsSupplierActionResult,
    SettingsSupplierPromptSnapshot,
    create_settings_supplier,
    load_settings_supplier_prompt_snapshot,
    toggle_settings_supplier,
    update_settings_supplier,
)


class SettingsSupplierActionServiceTests(unittest.TestCase):
    def test_load_settings_supplier_prompt_snapshot(self) -> None:
        supplier = SimpleNamespace(nombre="Acme", telefono="555", email="a@b.com", direccion="Centro")
        session = SimpleNamespace(get=lambda model, item_id: supplier if item_id == 4 else None)

        with patch(
            "pos_uniformes.services.settings_supplier_action_service._resolve_settings_supplier_model",
            return_value=object(),
        ):
            snapshot = load_settings_supplier_prompt_snapshot(session, supplier_id=4)

        self.assertEqual(
            snapshot,
            SettingsSupplierPromptSnapshot("Acme", "555", "a@b.com", "Centro"),
        )

    def test_supplier_mutations(self) -> None:
        admin_user = object()
        supplier = SimpleNamespace(nombre="Acme", activo=False)
        session = SimpleNamespace(get=lambda model, item_id: admin_user if item_id == 1 else supplier if item_id == 4 else None)
        fake_service = SimpleNamespace(
            create_supplier=lambda **kwargs: SimpleNamespace(nombre="Acme"),
            update_supplier=lambda **kwargs: supplier,
            toggle_active=lambda _session, _admin, _supplier: supplier,
        )

        with patch(
            "pos_uniformes.services.settings_supplier_action_service._resolve_settings_supplier_action_dependencies",
            return_value=(fake_service, object()),
        ), patch(
            "pos_uniformes.services.settings_supplier_action_service._resolve_settings_supplier_update_dependencies",
            return_value=(fake_service, object(), object()),
        ):
            create_result = create_settings_supplier(
                session,
                admin_user_id=1,
                payload={"nombre": "Acme", "telefono": "", "email": "", "direccion": ""},
            )
            update_result = update_settings_supplier(
                session,
                admin_user_id=1,
                supplier_id=4,
                payload={"nombre": "Acme", "telefono": "", "email": "", "direccion": ""},
            )
            toggle_result = toggle_settings_supplier(session, admin_user_id=1, supplier_id=4)

        self.assertEqual(create_result, SettingsSupplierActionResult("Acme"))
        self.assertEqual(update_result, SettingsSupplierActionResult("Acme"))
        self.assertEqual(toggle_result, SettingsSupplierActionResult("Acme", "desactivado"))


if __name__ == "__main__":
    unittest.main()
