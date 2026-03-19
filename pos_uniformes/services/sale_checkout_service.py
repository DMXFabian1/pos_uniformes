"""Contexto de checkout para venta y resolucion post-confirmacion."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable


@dataclass(frozen=True)
class SaleClientCheckoutSnapshot:
    client: object | None = None
    previous_level: object | None = None
    previous_discount: Decimal | None = None
    previous_level_label: str = ""
    client_name_for_notice: str = ""


def load_sale_client_checkout_snapshot(
    session,
    *,
    selected_client_id: object,
) -> SaleClientCheckoutSnapshot:
    if selected_client_id in {None, ""}:
        return SaleClientCheckoutSnapshot()

    cliente_model, loyalty_service = _resolve_sale_checkout_dependencies()
    client = session.get(cliente_model, int(selected_client_id))
    if client is None:
        raise ValueError("No se pudo cargar el cliente seleccionado.")

    previous_level = loyalty_service.coerce_level(client.nivel_lealtad)
    previous_discount = Decimal(str(client.descuento_preferente or Decimal("0.00"))).quantize(Decimal("0.01"))
    previous_level_label = loyalty_service.visual_spec(previous_level).label
    return SaleClientCheckoutSnapshot(
        client=client,
        previous_level=previous_level,
        previous_discount=previous_discount,
        previous_level_label=previous_level_label,
        client_name_for_notice=str(client.nombre),
    )


def resolve_sale_loyalty_transition_notice(
    snapshot: SaleClientCheckoutSnapshot,
    *,
    build_notice: Callable[[str, str, str, Decimal], str],
) -> str:
    if snapshot.client is None or snapshot.previous_level is None or snapshot.previous_discount is None:
        return ""

    _cliente_model, loyalty_service = _resolve_sale_checkout_dependencies()
    updated_level = loyalty_service.coerce_level(snapshot.client.nivel_lealtad)
    updated_discount = Decimal(str(snapshot.client.descuento_preferente or Decimal("0.00"))).quantize(
        Decimal("0.01")
    )
    if updated_level == snapshot.previous_level and updated_discount == snapshot.previous_discount:
        return ""

    updated_label = loyalty_service.visual_spec(updated_level).label
    return build_notice(
        snapshot.client_name_for_notice,
        snapshot.previous_level_label,
        updated_label,
        updated_discount,
    )


def _resolve_sale_checkout_dependencies():
    from pos_uniformes.database.models import Cliente
    from pos_uniformes.services.loyalty_service import LoyaltyService

    return Cliente, LoyaltyService
