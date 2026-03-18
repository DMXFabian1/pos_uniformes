"""Carga y resolucion del cliente seleccionado en caja."""

from __future__ import annotations

from sqlalchemy import func, select

from pos_uniformes.database.models import Cliente
from pos_uniformes.services.loyalty_service import LoyaltyService
from pos_uniformes.services.sale_client_benefit_service import SaleClientBenefit, resolve_sale_client_benefit
from pos_uniformes.services.sale_client_sync_service import SaleClientSyncState, resolve_sale_client_sync_state


def find_active_sale_client_by_code(session, client_code: str) -> Cliente | None:
    normalized_code = client_code.strip().upper()
    if not normalized_code:
        return None
    return session.scalar(
        select(Cliente).where(
            func.upper(Cliente.codigo_cliente) == normalized_code,
            Cliente.activo.is_(True),
        )
    )


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


def load_sale_selected_client_discount_percent(
    session,
    *,
    selected_client_id: int | str | None,
    normalize_discount_value,
):
    benefit = load_sale_selected_client_benefit(
        session,
        selected_client_id=selected_client_id,
        normalize_discount_value=normalize_discount_value,
    )
    if benefit is None:
        return normalize_discount_value(0)
    return benefit.discount_percent


def resolve_sale_selected_client_sync_state(
    session,
    *,
    selected_client_id: int | str | None,
    normalize_discount_value,
) -> SaleClientSyncState:
    benefit = load_sale_selected_client_benefit(
        session,
        selected_client_id=selected_client_id,
        normalize_discount_value=normalize_discount_value,
    )
    if benefit is None:
        return resolve_sale_client_sync_state(
            has_selected_client=False,
            discount_percent=0,
            source_label="",
            normalize_discount_value=normalize_discount_value,
        )

    return resolve_sale_client_sync_state(
        has_selected_client=True,
        discount_percent=benefit.discount_percent,
        source_label=benefit.source_label,
        normalize_discount_value=normalize_discount_value,
    )
