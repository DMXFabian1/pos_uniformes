"""Entrega y cancelacion operativa de apartados."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayawayDeliveryResult:
    sale_folio: str


def deliver_layaway(session, *, layaway_id: int, user_id: int) -> LayawayDeliveryResult:
    apartado_service, usuario_model, venta_service = _resolve_layaway_closure_dependencies()
    usuario = session.get(usuario_model, user_id)
    apartado = apartado_service.obtener_apartado(session, layaway_id)
    if usuario is None or apartado is None:
        raise ValueError("No se pudo cargar el apartado seleccionado.")
    sale = venta_service.crear_confirmada_desde_apartado(
        session=session,
        usuario=usuario,
        apartado=apartado,
        folio=f"ENT-{apartado.folio}",
        observacion=f"Entrega de apartado {apartado.folio}",
    )
    apartado_service.entregar_apartado(session, apartado, usuario)
    return LayawayDeliveryResult(sale_folio=str(sale.folio))


def cancel_layaway(session, *, layaway_id: int, user_id: int, note: str | None = None) -> None:
    apartado_service, usuario_model, _venta_service = _resolve_layaway_closure_dependencies()
    usuario = session.get(usuario_model, user_id)
    apartado = apartado_service.obtener_apartado(session, layaway_id)
    if usuario is None or apartado is None:
        raise ValueError("No se pudo cargar el apartado seleccionado.")
    apartado_service.cancelar_apartado(
        session=session,
        apartado=apartado,
        usuario=usuario,
        observacion=note,
    )


def _resolve_layaway_closure_dependencies():
    from pos_uniformes.database.models import Usuario
    from pos_uniformes.services.apartado_service import ApartadoService
    from pos_uniformes.services.venta_service import VentaService

    return ApartadoService, Usuario, VentaService
