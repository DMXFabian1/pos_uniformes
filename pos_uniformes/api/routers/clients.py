"""Endpoints de clientes para la API movil."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.schemas.clients import ClienteOut
from pos_uniformes.database.models import Cliente

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])


@router.get("/by-qr/{codigo}", response_model=ClienteOut)
def get_client_by_qr(
    codigo: str,
    db: Session = Depends(get_db),
    _auth=Depends(get_current_employee),
) -> ClienteOut:
    """
    Busca un cliente por su codigo_cliente (contenido del QR escaneado).
    Endpoint principal del scanner de cliente en la PWA.
    El QR del cliente codifica directamente su codigo_cliente.
    """
    cliente = db.scalar(
        select(Cliente).where(
            func.upper(Cliente.codigo_cliente) == codigo.strip().upper()
        )
    )
    if cliente is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "cliente_no_encontrado", "message": "No se encontro cliente con ese codigo."}},
        )
    return ClienteOut(
        id=cliente.id,
        codigo_cliente=cliente.codigo_cliente,
        nombre=cliente.nombre,
        tipo_cliente=cliente.tipo_cliente.value,
        nivel_lealtad=cliente.nivel_lealtad.value,
        descuento_preferente=cliente.descuento_preferente,
        telefono=cliente.telefono,
    )
