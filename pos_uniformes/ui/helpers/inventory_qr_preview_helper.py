"""Estado visible para el panel QR de Inventario."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.utils.product_name import sanitize_product_display_name


@dataclass(frozen=True)
class InventoryQrPreviewView:
    button_label: str
    info_label: str
    status_text: str
    status_tone: str
    placeholder_text: str
    preview_available: bool


def build_empty_inventory_qr_preview_view() -> InventoryQrPreviewView:
    return InventoryQrPreviewView(
        button_label="Generar QR",
        info_label="",
        status_text="Sin seleccion",
        status_tone="neutral",
        placeholder_text="QR pendiente",
        preview_available=False,
    )


def build_pending_inventory_qr_preview_view(
    *,
    sku: str,
    product_name: str,
    talla: str,
    color: str,
) -> InventoryQrPreviewView:
    return InventoryQrPreviewView(
        button_label="Generar QR",
        info_label=_build_inventory_qr_info_label(
            sku=sku,
            product_name=product_name,
            talla=talla,
            color=color,
        ),
        status_text="QR pendiente. Genera la etiqueta cuando la necesites.",
        status_tone="warning",
        placeholder_text="QR pendiente",
        preview_available=False,
    )


def build_available_inventory_qr_preview_view(
    *,
    sku: str,
    product_name: str,
    talla: str,
    color: str,
    file_name: str,
) -> InventoryQrPreviewView:
    return InventoryQrPreviewView(
        button_label="Regenerar QR",
        info_label=_build_inventory_qr_info_label(
            sku=sku,
            product_name=product_name,
            talla=talla,
            color=color,
        ),
        status_text=f"QR disponible: {file_name}",
        status_tone="positive",
        placeholder_text="",
        preview_available=True,
    )


def build_error_inventory_qr_preview_view() -> InventoryQrPreviewView:
    return InventoryQrPreviewView(
        button_label="Generar QR",
        info_label="",
        status_text="Sin datos de QR",
        status_tone="muted",
        placeholder_text="QR pendiente",
        preview_available=False,
    )


def _build_inventory_qr_info_label(
    *,
    sku: str,
    product_name: str,
    talla: str,
    color: str,
) -> str:
    clean_product_name = sanitize_product_display_name(product_name)
    return f"{sku} | {clean_product_name} | talla {talla} | color {color}"
