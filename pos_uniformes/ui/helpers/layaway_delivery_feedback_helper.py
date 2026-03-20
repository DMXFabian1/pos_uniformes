"""Copy operativo para confirmar y cerrar entregas de apartados."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LayawayDeliveryFeedbackView:
    title: str
    message: str


def build_layaway_delivery_confirmation_view(snapshot) -> LayawayDeliveryFeedbackView:
    if Decimal(snapshot.balance_due) > Decimal("0.00"):
        intro = (
            "El apartado aun tiene saldo pendiente. Si continuas, primero se registrara el "
            "abono final y despues se entregara la mercancia.\n\n"
        )
    else:
        intro = "Se generara una venta final a partir del apartado seleccionado.\n\n"
    return LayawayDeliveryFeedbackView(
        title="Entregar apartado",
        message=(
            intro
            + 
            f"Folio: {snapshot.layaway_folio}\n"
            f"Cliente: {snapshot.customer_label}\n"
            f"Lineas: {snapshot.items_count}\n"
            f"Piezas: {snapshot.pieces_count}\n"
            f"Total: ${snapshot.total}\n"
            f"Abonado: ${snapshot.total_paid}\n"
            f"Saldo actual: ${snapshot.balance_due}\n\n"
            "El stock no cambiara en este paso porque la mercancia ya estaba reservada.\n\n"
            "Deseas continuar con la entrega?"
        ),
    )


def build_layaway_delivery_result_view(result) -> LayawayDeliveryFeedbackView:
    payment_line = ""
    if Decimal(result.payment_registered_amount) > Decimal("0.00"):
        payment_line = f"Abono final registrado: ${result.payment_registered_amount}\n"
    return LayawayDeliveryFeedbackView(
        title="Apartado entregado",
        message=(
            f"Se entrego el apartado {result.layaway_folio} y se genero la venta {result.sale_folio}.\n\n"
            f"Cliente: {result.customer_label}\n"
            f"Lineas: {result.items_count}\n"
            f"Piezas: {result.pieces_count}\n"
            f"Total final: ${result.total}\n\n"
            f"{payment_line}"
            "Puedes abrir el ticket de venta ahora mismo si quieres revisarlo o imprimirlo."
        ),
    )
