"""Schemas de ventas y tickets para la API movil."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class VentaDetalleOut(BaseModel):
    id: int
    sku_snapshot: str | None
    descripcion_snapshot: str | None
    cantidad: int
    precio_unitario: Decimal
    subtotal_linea: Decimal

    model_config = {"from_attributes": True}


class TicketOut(BaseModel):
    """Detalle completo de una venta confirmada."""
    id: int
    folio: str
    estado: str
    cliente_nombre: str | None
    subtotal: Decimal
    descuento_monto: Decimal
    total: Decimal
    confirmada_at: datetime | None
    created_at: datetime
    lineas: list[VentaDetalleOut]

    model_config = {"from_attributes": True}


class TicketListItem(BaseModel):
    """Item compacto para listado de tickets."""
    id: int
    folio: str
    estado: str
    cliente_nombre: str | None
    total: Decimal
    confirmada_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumenVentasHoy(BaseModel):
    """Resumen de ventas del dia de la empleada."""
    total_ventas: int
    total_tickets: int
    monto_total: Decimal
    fecha: str
