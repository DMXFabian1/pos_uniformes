"""Schemas de clientes para la API movil."""

from __future__ import annotations

from pydantic import BaseModel


class ClienteOut(BaseModel):
    """E1-C4: lo que ve la vendedora al escanear. Sin nivel, sin descuento y
    con el telefono enmascarado (P2, D5)."""

    id: int
    codigo_cliente: str
    nombre: str
    tipo: str | None
    telefono_enmascarado: str

    model_config = {"from_attributes": True}
