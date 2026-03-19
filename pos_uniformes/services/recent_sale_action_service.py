"""Acciones operativas sobre ventas recientes."""

from __future__ import annotations


def cancel_recent_sale(session, *, sale_id: int, admin_user_id: int) -> None:
    venta_service, venta_model, usuario_model = _resolve_recent_sale_action_dependencies()
    sale = session.get(venta_model, sale_id)
    admin = session.get(usuario_model, admin_user_id)
    if sale is None or admin is None:
        raise ValueError("Venta o usuario ADMIN no encontrado.")
    venta_service.cancelar_venta(
        session=session,
        venta=sale,
        admin_usuario=admin,
        observacion="Cancelacion desde interfaz POS.",
    )


def _resolve_recent_sale_action_dependencies():
    from pos_uniformes.database.models import Usuario, Venta
    from pos_uniformes.services.venta_service import VentaService

    return VentaService, Venta, Usuario
