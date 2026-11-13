"""Contexto de checkout para venta en la Caja antigua.

2026-11-12: se retiró el aviso de cambio de nivel después de cobrar («el
nivel viejo retíralo», Daniel). La venta ya no revisa `nivel_lealtad`, así
que no hay transición que avisar; el snapshot solo carga al cliente.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SaleClientCheckoutSnapshot:
    client: object | None = None
    client_name_for_notice: str = ""


def load_sale_client_checkout_snapshot(
    session,
    *,
    selected_client_id: object,
) -> SaleClientCheckoutSnapshot:
    if selected_client_id in {None, ""}:
        return SaleClientCheckoutSnapshot()

    cliente_model = _resolve_sale_checkout_dependencies()
    client = session.get(cliente_model, int(selected_client_id))
    if client is None:
        raise ValueError("No se pudo cargar el cliente seleccionado.")

    return SaleClientCheckoutSnapshot(
        client=client,
        client_name_for_notice=str(client.nombre),
    )


def _resolve_sale_checkout_dependencies():
    from pos_uniformes.database.models import Cliente

    return Cliente
