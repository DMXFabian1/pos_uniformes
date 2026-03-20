"""Entrega y cancelacion operativa de apartados."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LayawayDeliveryConfirmation:
    layaway_id: int
    layaway_folio: str
    customer_label: str
    items_count: int
    pieces_count: int
    total: Decimal
    total_paid: Decimal
    balance_due: Decimal


@dataclass(frozen=True)
class LayawayDeliveryResult:
    layaway_folio: str
    sale_folio: str
    customer_label: str
    items_count: int
    pieces_count: int
    total: Decimal
    payment_registered_amount: Decimal


def load_layaway_delivery_confirmation(session, *, layaway_id: int) -> LayawayDeliveryConfirmation:
    apartado_service, _usuario_model, _venta_service = _resolve_layaway_closure_dependencies()
    apartado = apartado_service.obtener_apartado(session, layaway_id)
    if apartado is None:
        raise ValueError("No se pudo cargar el apartado seleccionado.")
    customer_label = (
        f"{apartado.cliente.codigo_cliente} · {apartado.cliente_nombre}"
        if getattr(apartado, "cliente", None) is not None
        else f"Manual · {apartado.cliente_nombre}"
    )
    details = getattr(apartado, "detalles", []) or []
    return LayawayDeliveryConfirmation(
        layaway_id=int(getattr(apartado, "id", layaway_id)),
        layaway_folio=str(apartado.folio),
        customer_label=customer_label,
        items_count=len(details),
        pieces_count=sum(int(getattr(detail, "cantidad", 0) or 0) for detail in details),
        total=Decimal(getattr(apartado, "total", 0) or 0).quantize(Decimal("0.01")),
        total_paid=Decimal(getattr(apartado, "total_abonado", 0) or 0).quantize(Decimal("0.01")),
        balance_due=Decimal(getattr(apartado, "saldo_pendiente", 0) or 0).quantize(Decimal("0.01")),
    )


def deliver_layaway(session, *, layaway_id: int, user_id: int) -> LayawayDeliveryResult:
    apartado_service, usuario_model, venta_service = _resolve_layaway_closure_dependencies()
    usuario = session.get(usuario_model, user_id)
    apartado = apartado_service.obtener_apartado(session, layaway_id)
    if usuario is None or apartado is None:
        raise ValueError("No se pudo cargar el apartado seleccionado.")
    return _finalize_layaway_delivery(
        session=session,
        apartado_service=apartado_service,
        venta_service=venta_service,
        apartado=apartado,
        usuario=usuario,
        payment_registered_amount=Decimal("0.00"),
    )


def settle_and_deliver_layaway(session, *, layaway_id: int, user_id: int, payment_input) -> LayawayDeliveryResult:
    apartado_service, usuario_model, venta_service = _resolve_layaway_closure_dependencies()
    usuario = session.get(usuario_model, user_id)
    apartado = apartado_service.obtener_apartado(session, layaway_id)
    if usuario is None or apartado is None:
        raise ValueError("No se pudo cargar el apartado seleccionado.")
    apartado_service.registrar_abono(
        session=session,
        apartado=apartado,
        usuario=usuario,
        monto=payment_input.amount,
        metodo_pago=payment_input.payment_method,
        monto_efectivo=payment_input.cash_amount,
        referencia=payment_input.reference or None,
        observacion=payment_input.notes or None,
    )
    return _finalize_layaway_delivery(
        session=session,
        apartado_service=apartado_service,
        venta_service=venta_service,
        apartado=apartado,
        usuario=usuario,
        payment_registered_amount=Decimal(payment_input.amount).quantize(Decimal("0.01")),
    )


def _finalize_layaway_delivery(
    *,
    session,
    apartado_service,
    venta_service,
    apartado,
    usuario,
    payment_registered_amount: Decimal,
) -> LayawayDeliveryResult:
    sale = venta_service.crear_confirmada_desde_apartado(
        session=session,
        usuario=usuario,
        apartado=apartado,
        folio=f"ENT-{apartado.folio}",
        observacion=f"Entrega de apartado {apartado.folio}",
    )
    apartado_service.entregar_apartado(session, apartado, usuario)
    customer_label = (
        f"{apartado.cliente.codigo_cliente} · {apartado.cliente_nombre}"
        if getattr(apartado, "cliente", None) is not None
        else f"Manual · {apartado.cliente_nombre}"
    )
    details = getattr(apartado, "detalles", []) or []
    return LayawayDeliveryResult(
        layaway_folio=str(apartado.folio),
        sale_folio=str(sale.folio),
        customer_label=customer_label,
        items_count=len(details),
        pieces_count=sum(int(getattr(detail, "cantidad", 0) or 0) for detail in details),
        total=Decimal(getattr(apartado, "total", 0) or 0).quantize(Decimal("0.01")),
        payment_registered_amount=payment_registered_amount,
    )


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
