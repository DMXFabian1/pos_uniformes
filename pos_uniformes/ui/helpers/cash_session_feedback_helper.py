"""Mensajes visibles para sesion y corte de caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CashSessionFeedbackView:
    title: str
    message: str


def build_cash_session_gate_feedback(
    *,
    requires_cut: bool,
    opened_at_label: str,
    opened_by: str,
    opening_amount: Decimal,
) -> CashSessionFeedbackView:
    if requires_cut:
        return CashSessionFeedbackView(
            title="Caja pendiente de corte",
            message=(
                "Se detecto una caja abierta de un dia anterior.\n\n"
                "Debes realizar el corte antes de registrar ventas, apartados o abonos.\n\n"
                f"Apertura: {opened_at_label}\n"
                f"Abierta por: {opened_by}\n"
                f"Reactivo inicial: ${opening_amount.quantize(Decimal('0.01'))}"
            ),
        )
    return CashSessionFeedbackView(
        title="Caja abierta detectada",
        message=(
            "Ya existe una caja abierta. Se reanudara la sesion actual.\n\n"
            f"Apertura: {opened_at_label}\n"
            f"Abierta por: {opened_by}\n"
            f"Reactivo inicial: ${opening_amount.quantize(Decimal('0.01'))}"
        ),
    )


def build_cash_movement_success_feedback(*, movement_type, amount: Decimal, target_total: object) -> CashSessionFeedbackView:
    movement_label = getattr(movement_type, "value", str(movement_type))
    labels = {
        "REACTIVO": "Ajuste de reactivo",
        "INGRESO": "Ingreso",
        "RETIRO": "Retiro",
        "reactivo": "Ajuste de reactivo",
        "ingreso": "Ingreso",
        "retiro": "Retiro",
    }
    label = labels.get(movement_label, str(movement_label))
    if "reactivo" in movement_label.lower():
        return CashSessionFeedbackView(
            title="Movimiento registrado",
            message=f"{label} ajustado correctamente. Total objetivo: ${target_total}.",
        )
    return CashSessionFeedbackView(
        title="Movimiento registrado",
        message=f"{label} por ${Decimal(amount).quantize(Decimal('0.01'))} registrado correctamente.",
    )


def build_cash_opening_correction_success_feedback(*, previous_amount: Decimal, new_amount: Decimal) -> CashSessionFeedbackView:
    return CashSessionFeedbackView(
        title="Apertura corregida",
        message=(
            f"Reactivo inicial actualizado de ${previous_amount.quantize(Decimal('0.01'))} "
            f"a ${new_amount.quantize(Decimal('0.01'))}."
        ),
    )


def build_cash_close_success_feedback(*, expected_amount: Decimal, counted_amount: Decimal, difference: Decimal) -> CashSessionFeedbackView:
    return CashSessionFeedbackView(
        title="Caja cerrada",
        message=(
            "El corte se registro correctamente.\n"
            f"Esperado: ${expected_amount.quantize(Decimal('0.01'))} | "
            f"Contado: ${counted_amount.quantize(Decimal('0.01'))} | "
            f"Diferencia: ${difference.quantize(Decimal('0.01'))}"
        ),
    )
