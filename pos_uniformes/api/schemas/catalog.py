"""Schemas de catalogo de productos para la API movil."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


# ── Guided catalog ────────────────────────────────────────────────────────────

class FiltroItem(BaseModel):
    id: int
    nombre: str


class EscuelaItem(BaseModel):
    id: int
    nombre: str


class NivelItem(BaseModel):
    id: int
    nombre: str
    escuelas: list[EscuelaItem]


class GuidedOptionsOut(BaseModel):
    niveles: list[NivelItem]
    tipo_pieza_school: list[FiltroItem]
    tipo_pieza_basics: list[FiltroItem]


class VarianteFamilyOut(BaseModel):
    id: int
    sku: str
    talla: str
    color: str
    precio_venta: Decimal
    stock_actual: int


class ProductFamilyOut(BaseModel):
    key: str
    nombre_base: str
    tipo_pieza: str | None
    tipo_pieza_id: int | None
    precio_desde: Decimal
    variantes: list[VarianteFamilyOut]


class GuidedProductsOut(BaseModel):
    genero_options: list[str]
    tipo_prenda_options: list[str]
    tipo_pieza_options: list[FiltroItem]
    families: list[ProductFamilyOut]


# ── Base schemas ──────────────────────────────────────────────────────────────

class VarianteOut(BaseModel):
    id: int
    sku: str
    talla: str
    color: str
    precio_venta: Decimal
    stock_actual: int

    model_config = {"from_attributes": True}


class VarianteScanOut(BaseModel):
    """Respuesta enriquecida del scanner — incluye datos del producto padre."""
    id: int
    sku: str
    talla: str
    color: str
    precio_venta: Decimal
    stock_actual: int
    # Datos del producto padre
    nombre: str
    categoria: str
    marca: str
    descripcion: str | None = None

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
