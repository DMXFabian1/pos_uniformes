"""Helpers visibles para las acciones contextuales de inventario.

El mismo menú sirve en «Por talla» (siempre una talla) y en «Por prenda»
(una prenda elegida son todas sus tallas). Con varias tallas elegidas, las
acciones de UNA talla se apagan, igual que la ficha de «Por talla» cuando
eliges varias (ahí solo quedan las acciones de lote de la barra): imprimir
pasa a imprimir todas y corregir existencia pasa a corregirlas en lote.
Las dos de lote siguen los permisos de la barra de lote: solo ADMIN.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Llave de «Corregir existencias» en lote (solo con varias tallas elegidas).
ACCION_CORREGIR_LOTE = "adjust_bulk"
#: Lo que se le agrega a una acción de una sola talla cuando hay varias.
TEXTO_ELIGE_UNA = " (elige una sola talla)"


@dataclass(frozen=True)
class InventoryContextMenuAction:
    key: str
    label: str
    enabled: bool


def build_inventory_context_menu_actions(
    *,
    is_admin: bool,
    variante_activa: bool,
    tallas_elegidas: int = 1,
) -> tuple[InventoryContextMenuAction, ...]:
    if tallas_elegidas > 1:
        return _acciones_varias_tallas(is_admin=is_admin, cantidad=tallas_elegidas)
    return (
        InventoryContextMenuAction(
            key="edit",
            label="Editar talla",
            enabled=is_admin,
        ),
        InventoryContextMenuAction(
            key="entry",
            label="Registrar entrada",
            enabled=is_admin,
        ),
        InventoryContextMenuAction(
            key="adjust",
            label="Corregir existencia",
            enabled=is_admin,
        ),
        InventoryContextMenuAction(
            key="print",
            label="Imprimir etiqueta",
            enabled=True,
        ),
        InventoryContextMenuAction(
            key="toggle",
            label="Activar esta talla" if not variante_activa else "Desactivar esta talla…",
            enabled=is_admin,
        ),
    )


def _acciones_varias_tallas(*, is_admin: bool, cantidad: int) -> tuple[InventoryContextMenuAction, ...]:
    """Mismo orden que con una talla; lo que es de una sola talla queda apagado."""
    return (
        InventoryContextMenuAction(key="edit", label="Editar talla" + TEXTO_ELIGE_UNA, enabled=False),
        InventoryContextMenuAction(key="entry", label="Registrar entrada" + TEXTO_ELIGE_UNA, enabled=False),
        InventoryContextMenuAction(
            key=ACCION_CORREGIR_LOTE,
            label=f"Corregir existencias ({cantidad:,} tallas)",
            enabled=is_admin,
        ),
        InventoryContextMenuAction(
            key="print",
            label=f"Imprimir {cantidad:,} etiquetas",
            # Igual que la barra de lote (inventory_print_label_button solo ADMIN).
            enabled=is_admin,
        ),
        InventoryContextMenuAction(key="toggle", label="Activar o desactivar talla" + TEXTO_ELIGE_UNA, enabled=False),
    )


def accion_contextual_permitida(
    action_specs: tuple[InventoryContextMenuAction, ...],
    llave: str | None,
) -> str | None:
    """La llave elegida solo si existe y está encendida en el menú; si no, None."""
    for spec in action_specs:
        if spec.key == llave:
            return llave if spec.enabled else None
    return None


def resolve_inventory_context_action_key(
    action_map: dict[str, object],
    chosen_action: object,
) -> str | None:
    for key, action in action_map.items():
        if action == chosen_action:
            return key
    return None
