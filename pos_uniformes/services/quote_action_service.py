"""Acciones operativas sobre presupuestos seleccionados."""

from __future__ import annotations


def cancel_quote(session, *, quote_id: int, user_id: int) -> None:
    presupuesto_service, usuario_model = _resolve_quote_action_dependencies()
    presupuesto = presupuesto_service.obtener_presupuesto(session, quote_id)
    usuario = session.get(usuario_model, user_id)
    if presupuesto is None or usuario is None:
        raise ValueError("No se pudo cargar el presupuesto seleccionado.")
    presupuesto_service.cancelar_presupuesto(
        session=session,
        presupuesto=presupuesto,
        usuario=usuario,
        observacion=f"Cancelado desde interfaz por {usuario.username}.",
    )


def _resolve_quote_action_dependencies():
    from pos_uniformes.database.models import Usuario
    from pos_uniformes.services.presupuesto_service import PresupuestoService

    return PresupuestoService, Usuario
