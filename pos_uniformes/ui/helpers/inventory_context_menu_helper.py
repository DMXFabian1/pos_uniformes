"""Helpers visibles para las acciones contextuales de inventario."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InventoryContextMenuAction:
    key: str
    label: str
    enabled: bool


def build_inventory_context_menu_actions(
    *,
    is_admin: bool,
    qr_exists: bool,
    variante_activa: bool,
) -> tuple[InventoryContextMenuAction, ...]:
    return (
        InventoryContextMenuAction(
            key="edit",
            label="Editar presentacion",
            enabled=is_admin,
        ),
        InventoryContextMenuAction(
            key="entry",
            label="Registrar entrada",
            enabled=is_admin,
        ),
        InventoryContextMenuAction(
            key="adjust",
            label="Corregir stock",
            enabled=is_admin,
        ),
        InventoryContextMenuAction(
            key="qr",
            label="Regenerar QR" if qr_exists else "Generar QR",
            enabled=True,
        ),
        InventoryContextMenuAction(
            key="print",
            label="Imprimir etiqueta",
            enabled=is_admin,
        ),
        InventoryContextMenuAction(
            key="toggle",
            label="Activar presentacion" if not variante_activa else "Desactivar presentacion",
            enabled=is_admin,
        ),
    )
