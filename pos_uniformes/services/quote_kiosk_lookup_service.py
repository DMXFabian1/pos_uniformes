"""Snapshot reutilizable para consulta rapida del kiosko de Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pos_uniformes.database.models import Producto, Variante


@dataclass(frozen=True)
class QuoteKioskLookupSnapshot:
    sku: str
    product_name: str
    school_name: str
    garment_type_name: str
    piece_type_name: str
    size_label: str
    color_label: str
    price: Decimal
    stock_actual: int
    location_label: str
    description_text: str
    origin_label: str


def load_quote_kiosk_lookup_snapshot(session, *, sku: str) -> QuoteKioskLookupSnapshot:
    normalized_sku = sku.strip().upper()
    if not normalized_sku:
        raise ValueError("Escanea o captura un SKU para consultarlo.")

    statement = (
        select(Variante)
        .options(
            joinedload(Variante.producto).joinedload(Producto.escuela),
            joinedload(Variante.producto).joinedload(Producto.tipo_prenda),
            joinedload(Variante.producto).joinedload(Producto.tipo_pieza),
        )
        .where(Variante.sku == normalized_sku, Variante.activo.is_(True))
    )
    variant = session.scalar(statement)
    if variant is None:
        raise ValueError(f"No existe una presentacion activa para el SKU '{normalized_sku}'.")
    if not variant.producto.activo:
        raise ValueError(f"El producto del SKU '{normalized_sku}' no esta activo.")

    product = variant.producto
    return QuoteKioskLookupSnapshot(
        sku=str(variant.sku),
        product_name=str(product.nombre_base),
        school_name=str(product.escuela.nombre if product.escuela else "General"),
        garment_type_name=str(product.tipo_prenda.nombre if product.tipo_prenda else "Sin tipo de prenda"),
        piece_type_name=str(product.tipo_pieza.nombre if product.tipo_pieza else "Sin tipo de pieza"),
        size_label=str(variant.talla),
        color_label=str(variant.color),
        price=Decimal(str(variant.precio_venta)).quantize(Decimal("0.01")),
        stock_actual=int(variant.stock_actual),
        location_label=str(product.ubicacion or "Sin ubicacion"),
        description_text=str(product.descripcion or ""),
        origin_label="Legacy" if bool(variant.origen_legacy) else "Catalogo actual",
    )
