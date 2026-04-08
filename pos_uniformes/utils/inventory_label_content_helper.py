"""Contenido visible de etiquetas segun familia de producto."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.ui.helpers.catalog_product_form_mode_helper import UNIFORM_CATEGORIES


@dataclass(frozen=True)
class InventoryLabelProfile:
    family: str
    show_price: bool


def resolve_inventory_label_profile(variante) -> InventoryLabelProfile:
    producto = getattr(variante, "producto", None)
    category_name = str(getattr(getattr(producto, "categoria", None), "nombre", "") or "").strip().casefold()
    garment_type = str(getattr(getattr(producto, "tipo_prenda", None), "nombre", "") or "").strip().casefold()
    has_school_context = bool(
        getattr(producto, "escuela_id", None)
        or str(getattr(getattr(producto, "escuela", None), "nombre", "") or "").strip()
        or getattr(producto, "nivel_educativo_id", None)
        or str(getattr(getattr(producto, "nivel_educativo", None), "nombre", "") or "").strip()
        or str(getattr(producto, "escudo", "") or "").strip()
    )
    is_uniform_family = (
        has_school_context
        or category_name in UNIFORM_CATEGORIES
        or garment_type in {"oficial", "deportivo", "escolta"}
    )
    if is_uniform_family:
        return InventoryLabelProfile(family="uniforme", show_price=False)
    return InventoryLabelProfile(family="ropa_normal", show_price=True)


def build_inventory_label_price_line(variante) -> str:
    price = Decimal(str(getattr(variante, "precio_venta", "0.00") or "0.00")).quantize(Decimal("0.01"))
    return f"Precio: ${price}"
