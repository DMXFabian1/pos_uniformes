"""Confirmacion operativa de venta en Caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable


@dataclass(frozen=True)
class SaleCheckoutResult:
    folio: str
    total: Decimal
    payment_method: str
    loyalty_transition_notice: str


def complete_sale_checkout(
    session,
    *,
    user_id: int,
    folio: str,
    sale_cart: list[dict[str, object]],
    subtotal: Decimal,
    discount_percent: Decimal,
    applied_discount: Decimal,
    total: Decimal,
    selected_client_id: object,
    breakdown: dict[str, object],
    payment_method: str,
    note_parts: list[str],
    build_notice: Callable[[str, str, str, Decimal], str],
) -> SaleCheckoutResult:
    (
        usuario_model,
        venta_service,
        venta_item_input,
        manual_promo_service,
        sale_checkout_service,
    ) = _resolve_sale_checkout_action_dependencies()

    usuario = session.get(usuario_model, user_id)
    if usuario is None:
        raise ValueError("Usuario no encontrado.")

    client_snapshot = sale_checkout_service.load_sale_client_checkout_snapshot(
        session,
        selected_client_id=selected_client_id,
    )
    cliente = client_snapshot.client
    venta = venta_service.crear_borrador(
        session=session,
        usuario=usuario,
        folio=folio,
        items=[
            venta_item_input(sku=str(item["sku"]), cantidad=int(item["cantidad"]))
            for item in sale_cart
        ],
        observacion=" | ".join(note_parts),
        cliente=cliente,
    )
    venta.subtotal = subtotal
    venta.descuento_porcentaje = discount_percent
    venta.descuento_monto = applied_discount
    venta.total = total
    venta_service.confirmar_venta(session, venta)

    loyalty_discount = Decimal(str(breakdown["loyalty_discount"] or Decimal("0.00"))).quantize(Decimal("0.01"))
    promo_discount = Decimal(str(breakdown["promo_discount"] or Decimal("0.00"))).quantize(Decimal("0.01"))
    if promo_discount > Decimal("0.00"):
        manual_promo_service.log_authorized_promo(
            session,
            venta=venta,
            actor_user=usuario,
            cliente=cliente,
            loyalty_percent=loyalty_discount,
            promo_percent=promo_discount,
            applied_percent=discount_percent,
            applied_source=str(breakdown["winner_source"]),
            note="Promocion manual autorizada con codigo en caja.",
        )

    loyalty_transition_notice = sale_checkout_service.resolve_sale_loyalty_transition_notice(
        client_snapshot,
        build_notice=build_notice,
    )
    return SaleCheckoutResult(
        folio=folio,
        total=total,
        payment_method=payment_method,
        loyalty_transition_notice=loyalty_transition_notice,
    )


def _resolve_sale_checkout_action_dependencies():
    from pos_uniformes.database.models import Usuario
    from pos_uniformes.services.manual_promo_service import ManualPromoService
    from pos_uniformes.services.venta_service import VentaItemInput, VentaService
    from pos_uniformes.services import sale_checkout_service

    return Usuario, VentaService, VentaItemInput, ManualPromoService, sale_checkout_service
