"""Carga y resolucion del cliente seleccionado en caja."""

from __future__ import annotations

from pos_uniformes.database.models import Cliente
from pos_uniformes.services.loyalty_service import LoyaltyService
from pos_uniformes.services.sale_client_benefit_service import SaleClientBenefit, resolve_sale_client_benefit


def load_sale_selected_client_benefit(
    session,
    *,
    selected_client_id: int | str | None,
    normalize_discount_value,
) -> SaleClientBenefit | None:
    if selected_client_id in {None, ""}:
        return None

    client = session.get(Cliente, int(selected_client_id))
    if client is None:
        return None

    return resolve_sale_client_benefit(
        preferred_discount=client.descuento_preferente,
        loyalty_level=client.nivel_lealtad,
        loyalty_discount_resolver=lambda level: LoyaltyService.discount_for_level(level, session=session),
        normalize_discount_value=normalize_discount_value,
    )
