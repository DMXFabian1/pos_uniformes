"""Popup reutilizable para acciones contextuales de Inventario."""

from __future__ import annotations

from PyQt6.QtWidgets import QMenu

from pos_uniformes.ui.helpers.inventory_context_menu_helper import (
    InventoryContextMenuAction,
    resolve_inventory_context_action_key,
)


def prompt_inventory_context_action(
    parent,
    *,
    global_pos,
    action_specs: tuple[InventoryContextMenuAction, ...],
) -> str | None:
    menu = QMenu(parent)
    action_map: dict[str, object] = {}
    for action_spec in action_specs:
        action = menu.addAction(action_spec.label)
        action.setEnabled(action_spec.enabled)
        action_map[action_spec.key] = action

    chosen_action = menu.exec(global_pos)
    return resolve_inventory_context_action_key(action_map, chosen_action)
