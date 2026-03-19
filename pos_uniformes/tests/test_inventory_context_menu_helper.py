from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.inventory_context_menu_helper import (
    build_inventory_context_menu_actions,
    resolve_inventory_context_action_key,
)


class InventoryContextMenuHelperTests(unittest.TestCase):
    def test_builds_admin_actions_with_regenerate_qr_and_disable_toggle(self) -> None:
        actions = build_inventory_context_menu_actions(
            is_admin=True,
            qr_exists=True,
            variante_activa=True,
        )

        self.assertEqual(
            [(action.key, action.label, action.enabled) for action in actions],
            [
                ("edit", "Editar presentacion", True),
                ("entry", "Registrar entrada", True),
                ("adjust", "Corregir stock", True),
                ("qr", "Regenerar QR", True),
                ("print", "Imprimir etiqueta", True),
                ("toggle", "Desactivar presentacion", True),
            ],
        )

    def test_builds_non_admin_actions_with_generate_qr_and_activate_toggle_disabled(self) -> None:
        actions = build_inventory_context_menu_actions(
            is_admin=False,
            qr_exists=False,
            variante_activa=False,
        )

        self.assertEqual(
            [(action.key, action.label, action.enabled) for action in actions],
            [
                ("edit", "Editar presentacion", False),
                ("entry", "Registrar entrada", False),
                ("adjust", "Corregir stock", False),
                ("qr", "Generar QR", True),
                ("print", "Imprimir etiqueta", False),
                ("toggle", "Activar presentacion", False),
            ],
        )

    def test_resolve_inventory_context_action_key_returns_matching_key(self) -> None:
        edit_action = object()
        qr_action = object()

        resolved = resolve_inventory_context_action_key(
            {
                "edit": edit_action,
                "qr": qr_action,
            },
            qr_action,
        )

        self.assertEqual(resolved, "qr")

    def test_resolve_inventory_context_action_key_returns_none_for_unknown_action(self) -> None:
        resolved = resolve_inventory_context_action_key(
            {
                "edit": object(),
            },
            object(),
        )

        self.assertIsNone(resolved)


if __name__ == "__main__":
    unittest.main()
