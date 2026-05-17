"""Creacion operativa de apartados desde dialogos de UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from pos_uniformes.utils.date_format import local_day_window
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
    seller_employee_code: str | None = None,
    seller_employee_display_name: str | None = None,
) -> LayawayCreationResult:
    apartado_service, cliente_model, usuario_model = _resolve_layaway_creation_dependencies()
    usuario = session.get(usuario_model, user_id)
    if usuario is None:
        raise ValueError("No se pudo cargar el usuario actual.")
    anticipo = Decimal(payload["anticipo"])
    if anticipo <= Decimal("0.00"):
        raise ValueError("El apartado debe iniciar con un anticipo mayor a cero.")

    cliente = None
    if payload["cliente_id"] is not None:
        cliente = session.get(cliente_model, int(payload["cliente_id"]))
        if cliente is None:
            raise ValueError("No se pudo cargar el cliente seleccionado.")

    due_value = None
    if payload["fecha_compromiso"]:
        due_date = date.fromisoformat(str(payload["fecha_compromiso"]))
        due_value = local_day_window(due_date)[0]

    emp_code = seller_employee_code or str(payload.get("seller_employee_code") or "") or None
    emp_name = seller_employee_display_name or str(payload.get("seller_employee_display_name") or "") or None
    layaway = apartado_service.crear_apartado(
        session=session,
        usuario=usuario,
        folio=folio,
        cliente_nombre=str(payload["cliente_nombre"]),
        cliente_telefono=str(payload["cliente_telefono"]),
        items=list(payload["items"]),
        anticipo=anticipo,
        fecha_compromiso=due_value,
        observacion=str(payload["observacion"]) or default_note,
        cliente=cliente,
        seller_employee_code=emp_code,
        seller_employee_display_name=emp_name,
    )
    return LayawayCreationResult(
        layaway_id=int(layaway.id),
        layaway_folio=str(layaway.folio),
    )


def _resolve_layaway_creation_dependencies():
    from pos_uniformes.database.models import Cliente, Usuario
    from pos_uniformes.services.apartado_service import ApartadoService

    return ApartadoService, Cliente, Usuario
