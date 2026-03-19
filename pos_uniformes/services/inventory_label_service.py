"""Carga y render de etiquetas de inventario."""

from __future__ import annotations

from dataclasses import dataclass

from pos_uniformes.database.models import Variante
from pos_uniformes.utils.label_generator import LabelGenerator, LabelRenderResult
from pos_uniformes.utils.product_name import sanitize_product_display_name


@dataclass(frozen=True)
class InventoryLabelContext:
    variant_id: int
    sku: str
    product_name: str
    talla: str
    color: str


def load_inventory_label_context(session, variant_id: int) -> InventoryLabelContext:
    variante = session.get(Variante, int(variant_id))
    if variante is None:
        raise ValueError("Presentacion no encontrada.")

    return InventoryLabelContext(
        variant_id=int(variante.id),
        sku=str(variante.sku),
        product_name=sanitize_product_display_name(
            getattr(variante.producto, "nombre_base", None) or variante.producto.nombre
        ),
        talla=str(variante.talla),
        color=str(variante.color),
    )


def render_inventory_label(
    session,
    variant_id: int,
    *,
    mode: str,
    requested_copies: int,
) -> LabelRenderResult:
    variante = session.get(Variante, int(variant_id))
    if variante is None:
        raise ValueError("Presentacion no encontrada.")

    _ = variante.producto.nombre
    if variante.producto.escuela is not None:
        _ = variante.producto.escuela.nombre
    if variante.producto.nivel_educativo is not None:
        _ = variante.producto.nivel_educativo.nombre

    return LabelGenerator.render_for_variant(
        variante,
        mode=mode,
        requested_copies=requested_copies,
    )
