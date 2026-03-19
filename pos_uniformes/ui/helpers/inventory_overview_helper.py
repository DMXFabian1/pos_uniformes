"""Helpers visibles para la ficha rapida de la seleccion actual en inventario."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.utils.product_name import sanitize_product_display_name


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
        overview_label="Selecciona una presentacion",
        product_label="Elige una fila para ver su ficha rapida.",
        status_badge=InventoryBadgeState(text="Sin seleccion", tone="neutral"),
        stock_badge=InventoryBadgeState(text="Sin stock", tone="neutral"),
        stock_hint_label="",
        meta_label="",
        last_movement_label="",
        catalog_selection_label="Selecciona una presentacion en inventario para gestionar cambios.",
        toggle_product_label="Prod.",
        toggle_variant_label="Pres.",
    )


def build_error_inventory_overview_view() -> InventoryOverviewView:
    return InventoryOverviewView(
        overview_label="No se pudo cargar la presentacion seleccionada.",
        product_label="",
        status_badge=InventoryBadgeState(text="Error", tone="danger"),
        stock_badge=InventoryBadgeState(text="Sin stock", tone="neutral"),
        stock_hint_label="",
        meta_label="",
        last_movement_label="",
        catalog_selection_label="Selecciona una presentacion en inventario para gestionar cambios.",
        toggle_product_label="Prod.",
        toggle_variant_label="Pres.",
    )


def build_inventory_overview_view(
    *,
    sku: str,
    product_name: str,
    product_active: bool,
    variant_active: bool,
    stock_actual: int,
    apartado_cantidad: int,
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
) -> InventoryOverviewView:
    clean_product_name = sanitize_product_display_name(product_name)
    stock_status = "agotado" if stock_actual == 0 else "bajo" if stock_actual <= 3 else "saludable"
    stock_tone = "danger" if stock_actual == 0 else "warning" if stock_actual <= 3 else "positive"
    if movement_type is None or movement_quantity is None:
        last_movement_label = "Sin movimientos registrados."
    else:
        last_movement_label = f"Ultimo movimiento: {movement_type} | {movement_quantity:+} | {movement_date}"
    return InventoryOverviewView(
        overview_label=sku,
        product_label=clean_product_name,
        status_badge=InventoryBadgeState(
            text="ACTIVA" if variant_active else "INACTIVA",
            tone="positive" if variant_active else "muted",
        ),
        stock_badge=InventoryBadgeState(
            text=stock_status.capitalize(),
            tone=stock_tone,
        ),
        stock_hint_label=f"Talla {talla} | Color {color} | Precio {precio_venta} | {origen_etiqueta}",
        meta_label=f"Stock actual {stock_actual} | Apartado {apartado_cantidad} | Escuela {escuela_nombre}",
        last_movement_label=last_movement_label,
        catalog_selection_label=(
            f"{sku} | {clean_product_name} | {tipo_prenda_nombre} | {tipo_pieza_nombre} | "
            f"precio {precio_venta} | stock {stock_actual} | apartado {apartado_cantidad}"
        ),
        toggle_product_label="Activar prod." if not product_active else "Desactivar prod.",
        toggle_variant_label="Activar var." if not variant_active else "Desactivar var.",
    )
