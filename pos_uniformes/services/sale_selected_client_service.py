"""Carga y resolucion del cliente seleccionado en caja."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from sqlalchemy import func, select

from pos_uniformes.database.models import Cliente
from pos_uniformes.services.loyalty_service import LoyaltyService
from pos_uniformes.services.sale_client_benefit_service import SaleClientBenefit, resolve_sale_client_benefit
from pos_uniformes.services.sale_client_sync_service import SaleClientSyncState, resolve_sale_client_sync_state


SIN_NIVEL_LABEL = "Sin nivel"

_CLIENT_SCAN_TRANSLATION = str.maketrans(
    {
        "´": "-",
        "`": "-",
        "'": "-",
        "_": "-",
        "–": "-",
        "—": "-",
    }
)


def normalize_scanned_client_code(client_code: str) -> str:
    return client_code.strip().upper().translate(_CLIENT_SCAN_TRANSLATION)


def find_active_sale_client_by_code(session, client_code: str) -> Cliente | None:
    normalized_code = normalize_scanned_client_code(client_code)
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

    benefit = resolve_sale_client_benefit(
        preferred_discount=client.descuento_preferente,
        loyalty_level=client.nivel_lealtad,
        # E1-B (R3): un cliente SIN nivel no tiene descuento por nivel (0 %).
        # No se llama a `discount_for_level(None)`, que lo trataría como BASICO.
        loyalty_discount_resolver=lambda level: (
            Decimal("0.00") if level is None else LoyaltyService.discount_for_level(level, session=session)
        ),
        normalize_discount_value=normalize_discount_value,
    )
    if client.nivel_lealtad is None:
        # E1-B (R3): la etiqueta de un cliente sin nivel no dice «Basico».
        return replace(benefit, source_label=SIN_NIVEL_LABEL)
    return benefit


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
