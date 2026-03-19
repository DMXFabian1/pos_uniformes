"""Registro operativo de abonos de apartados."""

from __future__ import annotations


def register_layaway_payment(
    session,
    *,
    layaway_id: int,
    user_id: int,
    payment_input,
) -> None:
    apartado_service, usuario_model = _resolve_layaway_payment_action_dependencies()
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


def _resolve_layaway_payment_action_dependencies():
    from pos_uniformes.database.models import Usuario
    from pos_uniformes.services.apartado_service import ApartadoService

    return ApartadoService, Usuario
