"""Endpoints de clientes para la API movil."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.schemas.clients import ClienteOut
from pos_uniformes.database.models import Cliente, ClienteTipo
from pos_uniformes.services.clientes.telefono import enmascarar_telefono

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])
_logger = logging.getLogger(__name__)


def _programa_activo(db: Session, cliente_id: int) -> str | None:
    """E4-E: nombre del programa activo. Si la base aún no tiene programas
    (sin migrar), el escaneo sigue funcionando y solo no lo muestra."""
    from pos_uniformes.database.models import Membresia, Programa

    try:
        return db.scalar(
            select(Programa.nombre)
            .join(Membresia, Membresia.programa_id == Programa.id)
            .where(Membresia.cliente_id == int(cliente_id), Membresia.estado == "activa")
        )
    except SQLAlchemyError:
        _logger.debug("by-qr: no se pudo leer el programa del cliente %s", cliente_id, exc_info=True)
        db.rollback()
        return None


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

    E1-C4: una ficha inactiva o archivada responde 404, igual que una que no
    existe. La respuesta no lleva nivel ni descuento, y el telefono va
    enmascarado.
    """
    cliente = db.scalar(
        select(Cliente).where(
            func.upper(Cliente.codigo_cliente) == codigo.strip().upper()
        )
    )
    if cliente is None or not cliente.activo or cliente.archivado_en is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "cliente_no_encontrado", "message": "No se encontro cliente con ese codigo."}},
        )
    tipo = db.get(ClienteTipo, cliente.tipo_cliente_id) if cliente.tipo_cliente_id is not None else None
    return ClienteOut(
        id=cliente.id,
        codigo_cliente=cliente.codigo_cliente,
        nombre=cliente.nombre,
        tipo=tipo.nombre if tipo is not None else None,
        telefono_enmascarado=enmascarar_telefono(cliente.telefono),
        programa=_programa_activo(db, int(cliente.id)),
    )
