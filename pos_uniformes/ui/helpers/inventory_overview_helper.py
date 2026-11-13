"""Helpers visibles para la ficha rápida de la selección actual en Inventario."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.services.rebaja_service import fmt_corto
from pos_uniformes.ui.helpers.inventory_toggle_helper import etiqueta_boton_prenda, etiqueta_boton_talla
from pos_uniformes.utils.product_name import sanitize_product_display_name
from pos_uniformes.services.inventario_existencia_service import (
    AGOTADO,
    BAJO,
    BAJO_MINIMO,
    NEGATIVO,
    VIRTUAL,
    clasificar_existencia,
    es_conjunto_o_virtual,
    tono_existencia,
)

_ESTADO_FICHA = {
    VIRTUAL: "Conjunto",
    NEGATIVO: "En negativo",
    AGOTADO: "Agotada",
    BAJO_MINIMO: "Quedan pocas",
    BAJO: "Quedan pocas",
}
_ESTADO_FICHA_CON_EXISTENCIA = "Sí hay"

TEXTO_SIN_SELECCION = "Elige una talla"
TEXTO_SIN_SELECCION_DETALLE = "Toca una fila de la tabla para ver su ficha."
TEXTO_SELECCION_OCULTA = "Elige una talla en Inventario para hacer cambios."


@dataclass(frozen=True)
class InventoryBadgeState:
    text: str
    tone: str


@dataclass(frozen=True)
class InventoryOverviewView:
    overview_label: str
    product_label: str
    status_badge: InventoryBadgeState
    stock_badge: InventoryBadgeState
    stock_hint_label: str
    meta_label: str
    last_movement_label: str
    catalog_selection_label: str
    toggle_product_label: str
    toggle_variant_label: str


def build_empty_inventory_overview_view() -> InventoryOverviewView:
    return InventoryOverviewView(
        overview_label=TEXTO_SIN_SELECCION,
        product_label=TEXTO_SIN_SELECCION_DETALLE,
        status_badge=InventoryBadgeState(text="Sin selección", tone="neutral"),
        stock_badge=InventoryBadgeState(text="—", tone="neutral"),
        stock_hint_label="",
        meta_label="",
        last_movement_label="",
        catalog_selection_label=TEXTO_SELECCION_OCULTA,
        toggle_product_label=etiqueta_boton_prenda(True),
        toggle_variant_label=etiqueta_boton_talla(True),
    )


def build_error_inventory_overview_view() -> InventoryOverviewView:
    return InventoryOverviewView(
        overview_label="No se pudo cargar la talla elegida.",
        product_label="",
        status_badge=InventoryBadgeState(text="Error", tone="danger"),
        stock_badge=InventoryBadgeState(text="—", tone="neutral"),
        stock_hint_label="",
        meta_label="",
        last_movement_label="",
        catalog_selection_label=TEXTO_SELECCION_OCULTA,
        toggle_product_label=etiqueta_boton_prenda(True),
        toggle_variant_label=etiqueta_boton_talla(True),
    )


def build_inventory_overview_view(
    *,
    sku: str,
    product_name: str,
    product_active: bool,
    variant_active: bool,
    stock_actual: int,
    stock_minimo: int | None = None,
    talla: str,
    color: str,
    precio_venta: Decimal | str | int | float,
    origen_etiqueta: str,
    escuela_nombre: str,
    tipo_prenda_nombre: str,
    tipo_pieza_nombre: str,
    movement_type: str | None,
    movement_quantity: int | None,
    movement_date: str,
    es_conjunto: bool = False,
) -> InventoryOverviewView:
    clean_product_name = sanitize_product_display_name(product_name)
    virtual = es_conjunto_o_virtual(es_conjunto=es_conjunto, stock_minimo=stock_minimo)
    clase = clasificar_existencia(stock_actual, stock_minimo=stock_minimo, virtual=virtual)
    stock_status = _ESTADO_FICHA.get(clase, _ESTADO_FICHA_CON_EXISTENCIA)
    stock_tone = tono_existencia(stock_actual, stock_minimo=stock_minimo, virtual=virtual)
    if movement_type is None or movement_quantity is None:
        last_movement_label = "Sin movimientos todavía."
    else:
        last_movement_label = f"Último movimiento: {movement_type} {_con_signo(movement_quantity)} · {movement_date}"
    return InventoryOverviewView(
        overview_label=sku,
        product_label=clean_product_name,
        status_badge=_estado_badge(product_active=product_active, variant_active=variant_active),
        stock_badge=InventoryBadgeState(
            text=stock_status,
            tone=stock_tone,
        ),
        stock_hint_label=f"Talla {talla} · {color} · {_precio(precio_venta)}",
        meta_label=f"Hay {stock_actual} · {escuela_nombre}",
        last_movement_label=last_movement_label,
        catalog_selection_label=(
            f"{sku} | {clean_product_name} | {tipo_prenda_nombre} | {tipo_pieza_nombre} | "
            f"precio {precio_venta} | stock {stock_actual}"
        ),
        toggle_product_label=etiqueta_boton_prenda(product_active),
        toggle_variant_label=etiqueta_boton_talla(variant_active),
    )


def _estado_badge(*, product_active: bool, variant_active: bool) -> InventoryBadgeState:
    """Sin columna «Estado» en la tabla: la ficha dice si se vende o no."""
    if not product_active:
        return InventoryBadgeState(text="Prenda desactivada", tone="muted")
    if not variant_active:
        return InventoryBadgeState(text="Desactivada", tone="muted")
    return InventoryBadgeState(text="Activa", tone="positive")


def _precio(precio_venta) -> str:
    try:
        return fmt_corto(precio_venta)
    except Exception:  # noqa: BLE001
        return str(precio_venta)


def _con_signo(cantidad: int) -> str:
    """«+3» / «−1» (con el signo menos de verdad, como la tabla)."""
    return f"+{cantidad}" if cantidad > 0 else f"\u2212{abs(cantidad)}" if cantidad < 0 else "0"
