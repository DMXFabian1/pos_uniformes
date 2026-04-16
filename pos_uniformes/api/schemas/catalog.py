"""Schemas de catalogo de productos para la API movil."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class VarianteOut(BaseModel):
    id: int
    sku: str
    talla: str
    color: str
    precio_venta: Decimal
    stock_actual: int

    model_config = {"from_attributes": True}


class ProductoOut(BaseModel):
    id: int
    nombre: str
    categoria: str
    marca: str
    descripcion: str | None
    activo: bool
    variantes: list[VarianteOut]

    model_config = {"from_attributes": True}


class ProductoListItem(BaseModel):
    """Version compacta para listados."""
    id: int
    nombre: str
    categoria: str
    marca: str
    precio_desde: Decimal
    total_variantes: int

    model_config = {"from_attributes": True}


class CatalogPage(BaseModel):
    items: list[ProductoListItem]
    total: int
    page: int
    page_size: int
