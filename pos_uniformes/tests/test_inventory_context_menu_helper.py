from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.inventory_context_menu_helper import (
    ACCION_CORREGIR_LOTE,
    TEXTO_ELIGE_UNA,
    accion_contextual_permitida,
    build_inventory_context_menu_actions,
    resolve_inventory_context_action_key,
)


class InventoryContextMenuHelperTests(unittest.TestCase):
    def test_builds_admin_actions_without_qr_and_disable_toggle(self) -> None:
        actions = build_inventory_context_menu_actions(
            is_admin=True,
            variante_activa=True,
        )

        self.assertEqual(
            [(action.key, action.label, action.enabled) for action in actions],
            [
                ("edit", "Editar talla", True),
                ("entry", "Registrar entrada", True),
                ("adjust", "Corregir existencia", True),
                ("print", "Imprimir etiqueta", True),
                ("toggle", "Desactivar esta talla…", True),
            ],
        )

    def test_builds_non_admin_actions_without_qr_and_activate_toggle_disabled(self) -> None:
        actions = build_inventory_context_menu_actions(
            is_admin=False,
            variante_activa=False,
        )

        self.assertEqual(
            [(action.key, action.label, action.enabled) for action in actions],
            [
                ("edit", "Editar talla", False),
                ("entry", "Registrar entrada", False),
                ("adjust", "Corregir existencia", False),
                ("print", "Imprimir etiqueta", True),
                ("toggle", "Activar esta talla", False),
            ],
        )

    def test_una_talla_explicita_da_el_mismo_menu_de_por_talla(self) -> None:
        self.assertEqual(
            build_inventory_context_menu_actions(is_admin=True, variante_activa=True, tallas_elegidas=1),
            build_inventory_context_menu_actions(is_admin=True, variante_activa=True),
        )

    def test_varias_tallas_apaga_lo_de_una_sola_y_deja_el_lote(self) -> None:
        actions = build_inventory_context_menu_actions(is_admin=True, variante_activa=True, tallas_elegidas=4)

        self.assertEqual(
            [(action.key, action.label, action.enabled) for action in actions],
            [
                ("edit", "Editar talla" + TEXTO_ELIGE_UNA, False),
                ("entry", "Registrar entrada" + TEXTO_ELIGE_UNA, False),
                (ACCION_CORREGIR_LOTE, "Corregir existencias (4 tallas)", True),
                ("print", "Imprimir 4 etiquetas", True),
                ("toggle", "Activar o desactivar talla" + TEXTO_ELIGE_UNA, False),
            ],
        )

    def test_varias_tallas_sin_admin_no_deja_nada_como_la_barra_de_lote(self) -> None:
        # La barra de lote apaga «Imprimir etiquetas» para quien no es ADMIN;
        # el menú con varias tallas se porta igual.
        actions = build_inventory_context_menu_actions(is_admin=False, variante_activa=False, tallas_elegidas=2)

        self.assertEqual([action.key for action in actions if action.enabled], [])

    def test_una_talla_sin_admin_sigue_dejando_imprimir_como_antes(self) -> None:
        actions = build_inventory_context_menu_actions(is_admin=False, variante_activa=True)

        self.assertEqual([action.key for action in actions if action.enabled], ["print"])

    def test_accion_permitida_solo_si_esta_encendida(self) -> None:
        cajero = build_inventory_context_menu_actions(is_admin=False, variante_activa=True)
        self.assertEqual(accion_contextual_permitida(cajero, "print"), "print")
        self.assertIsNone(accion_contextual_permitida(cajero, "edit"))
        self.assertIsNone(accion_contextual_permitida(cajero, None))
        self.assertIsNone(accion_contextual_permitida(cajero, "no-existe"))
        lote_cajero = build_inventory_context_menu_actions(is_admin=False, variante_activa=True, tallas_elegidas=3)
        self.assertIsNone(accion_contextual_permitida(lote_cajero, "print"))
        lote_admin = build_inventory_context_menu_actions(is_admin=True, variante_activa=True, tallas_elegidas=3)
        self.assertEqual(accion_contextual_permitida(lote_admin, "print"), "print")

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
