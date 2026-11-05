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
    #: Si la etiqueta de esta prenda puede llevar precio: la ropa normal sí,
    #: los uniformes nunca (su precio cambia; para eso está el QR). Con esto la
    #: ventana ni siquiera ofrece «Mostrar precio» en un uniforme — antes salía
    #: marcado y no hacía nada (Daniel, 2026-11-05).
    precio_por_defecto: bool = True


def precio_por_defecto_de(variante) -> bool:
    from pos_uniformes.utils.inventory_label_content_helper import resolve_inventory_label_profile

    try:
        return bool(resolve_inventory_label_profile(variante).show_price)
    except Exception:  # noqa: BLE001 — ante la duda, como siempre
        return True


def precio_por_defecto_de_fila(row: dict) -> bool:
    """Lo mismo, desde una fila del catálogo en disco (kiosko sin conexión)."""
    try:
        return precio_por_defecto_de(_build_fake_variante_from_cache_row(row))
    except Exception:  # noqa: BLE001
        return True


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
        precio_por_defecto=precio_por_defecto_de(variante),
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
        # Lo pone quien llama (tiene el catálogo completo); sin dato, un color.
        multicolor=bool(row.get("producto_multicolor", False)),
    )
    return SimpleNamespace(
        sku=str(row["sku"]),
        talla=str(row.get("talla") or ""),
        color=str(row.get("color") or ""),
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
