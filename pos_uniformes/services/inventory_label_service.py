"""Carga y render de etiquetas de inventario."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace

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


def _build_fake_variante_from_cache_row(row: dict) -> SimpleNamespace:
    """Construye un objeto que imita Variante a partir de una fila del cache local."""
    escuela_nombre = str(row.get("escuela_nombre") or "")
    if escuela_nombre == "General":
        escuela_nombre = ""
    nivel_nombre = str(row.get("nivel_educativo_nombre") or "")
    if nivel_nombre == "Sin nivel":
        nivel_nombre = ""

    producto = SimpleNamespace(
        nombre=str(row.get("producto_nombre") or ""),
        nombre_base=row.get("producto_nombre_base"),
        escuela_id=row.get("escuela_id"),
        nivel_educativo_id=None if not nivel_nombre else "set",
        escuela=SimpleNamespace(nombre=escuela_nombre) if escuela_nombre else None,
        nivel_educativo=SimpleNamespace(nombre=nivel_nombre) if nivel_nombre else None,
        categoria=SimpleNamespace(nombre=str(row.get("categoria_nombre") or "")),
        tipo_prenda=SimpleNamespace(nombre=str(row.get("tipo_prenda_nombre") or "")),
        escudo=None,
    )
    return SimpleNamespace(
        sku=str(row["sku"]),
        talla=str(row.get("talla") or ""),
        precio_venta=Decimal(str(row.get("precio_venta") or "0")),
        producto=producto,
    )


def render_inventory_label_from_cache_row(
    row: dict,
    *,
    mode: str,
    requested_copies: int,
    show_price: bool | None = None,
) -> LabelRenderResult:
    """Renderiza una etiqueta directamente desde una fila del cache local (sin DB)."""
    fake_variante = _build_fake_variante_from_cache_row(row)
    return LabelGenerator.render_for_variant(
        fake_variante,
        mode=mode,
        requested_copies=requested_copies,
        show_price=show_price,
    )


def render_inventory_label(
    session,
    variant_id: int,
    *,
    mode: str,
    requested_copies: int,
    show_price: bool | None = None,
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
        show_price=show_price,
    )
