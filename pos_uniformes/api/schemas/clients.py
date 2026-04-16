"""Schemas de clientes para la API movil."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class ClienteOut(BaseModel):
    id: int
    codigo_cliente: str
    nombre: str
    tipo_cliente: str
    nivel_lealtad: str
    descuento_preferente: Decimal
    telefono: str | None

    model_config = {"from_attributes": True}
