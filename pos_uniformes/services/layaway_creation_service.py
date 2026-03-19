"""Creacion operativa de apartados desde dialogos de UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class LayawayCreationResult:
    layaway_id: int
    layaway_folio: str


def create_layaway_from_payload(
    session,
    *,
    user_id: int,
    folio: str,
    payload: dict[str, object],
    default_note: str | None = None,
) -> LayawayCreationResult:
    apartado_service, cliente_model, usuario_model = _resolve_layaway_creation_dependencies()
    usuario = session.get(usuario_model, user_id)
    if usuario is None:
        raise ValueError("No se pudo cargar el usuario actual.")

    cliente = None
    if payload["cliente_id"] is not None:
        cliente = session.get(cliente_model, int(payload["cliente_id"]))
        if cliente is None:
            raise ValueError("No se pudo cargar el cliente seleccionado.")

    due_value = None
    if payload["fecha_compromiso"]:
        due_date = date.fromisoformat(str(payload["fecha_compromiso"]))
        due_value = datetime.combine(due_date, datetime.min.time())

    layaway = apartado_service.crear_apartado(
        session=session,
        usuario=usuario,
        folio=folio,
        cliente_nombre=str(payload["cliente_nombre"]),
        cliente_telefono=str(payload["cliente_telefono"]),
        items=list(payload["items"]),
        anticipo=Decimal(payload["anticipo"]),
        fecha_compromiso=due_value,
        observacion=str(payload["observacion"]) or default_note,
        cliente=cliente,
    )
    return LayawayCreationResult(
        layaway_id=int(layaway.id),
        layaway_folio=str(layaway.folio),
    )


def _resolve_layaway_creation_dependencies():
    from pos_uniformes.database.models import Cliente, Usuario
    from pos_uniformes.services.apartado_service import ApartadoService

    return ApartadoService, Cliente, Usuario
