"""Schemas de presupuestos para la API movil."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


class LineaInput(BaseModel):
    """Una linea del presupuesto enviada desde el movil."""
    sku: str
    cantidad: int
    precio_unitario: Decimal

    @field_validator("cantidad")
    @classmethod
    def cantidad_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")
        return v

    @field_validator("precio_unitario")
    @classmethod
    def precio_no_negativo(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("El precio no puede ser negativo.")
        return v


class PresupuestoCreateRequest(BaseModel):
    cliente_id: int | None = None
    cliente_nombre: str | None = None
    observacion: str | None = None
    lineas: list[LineaInput] = []


class PresupuestoUpdateRequest(BaseModel):
    cliente_id: int | None = None
    cliente_nombre: str | None = None
    observacion: str | None = None
    lineas: list[LineaInput]


class LineaOut(BaseModel):
    id: int
    sku_snapshot: str
    descripcion_snapshot: str
    talla_snapshot: str | None
    color_snapshot: str | None
    precio_unitario: Decimal
    cantidad: int
    subtotal_linea: Decimal

    model_config = {"from_attributes": True}


class PresupuestoOut(BaseModel):
    id: int
    folio: str
    estado: str
    seller_employee_id: int | None
    cliente_id: int | None
    cliente_nombre: str | None
    subtotal: Decimal
    total: Decimal
    observacion: str | None
    lineas: list[LineaOut]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PresupuestoListItem(BaseModel):
    id: int
    folio: str
    estado: str
    cliente_nombre: str | None
    total: Decimal
    total_lineas: int
    created_at: datetime

    model_config = {"from_attributes": True}
