"""Mensajes visibles para sesion y corte de caja."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CashSessionFeedbackView:
    title: str
    message: str


def _format_elapsed(minutes: int) -> str:
    if minutes < 1:
        return "hace un momento"
    if minutes < 60:
        return f"hace {minutes} min"
    hours = minutes // 60
    remaining = minutes % 60
    if hours < 24:
        if remaining:
            return f"hace {hours}h {remaining}min"
        return f"hace {hours}h"
    days = hours // 24
    remaining_hours = hours % 24
    if days == 1:
        return f"hace 1 dia y {remaining_hours}h" if remaining_hours else "hace 1 dia"
    return f"hace {days} dias"


def _status_pill(text: str, tone: str) -> str:
    colors = {
        "ok": "color: #1a7f37; background: #dafbe1;",
        "warn": "color: #7a4f01; background: #fff8c5;",
        "error": "color: #cf222e; background: #ffebe9;",
    }
    style = colors.get(tone, "")
    return f'<span style="padding: 3px 10px; border-radius: 6px; font-weight: 700; font-size: 13px; {style}">{text}</span>'


def _info_row(label: str, value: str) -> str:
    return (
        f'<tr>'
        f'<td style="padding: 4px 14px 4px 0; color: #57606a; font-weight: 500;">{label}</td>'
        f'<td style="padding: 4px 0; font-weight: 600; color: #24292f;">{value}</td>'
        f'</tr>'
    )


def build_cash_session_gate_html(
    *,
    requires_cut: bool,
    opened_at_label: str,
    opened_by: str,
    opening_amount: Decimal,
    elapsed_minutes: int = 0,
) -> tuple[str, str]:
    elapsed_text = _format_elapsed(elapsed_minutes)

    if requires_cut:
        status = _status_pill("Corte pendiente", "error")
        title = "Caja pendiente de corte"
        note = (
            '<p style="color: #cf222e; font-weight: 600; margin-top: 10px;">'
            'Debes realizar el corte antes de registrar ventas, apartados o abonos.</p>'
        )
    else:
        status = _status_pill("Abierta", "ok")
        title = "Sesion de caja activa"
        note = (
            '<p style="color: #57606a; margin-top: 10px;">'
            'Se reanudara la sesion actual.</p>'
        )

    html = (
        f'<div style="font-size: 13px;">'
        f'<p style="margin-bottom: 12px;">{status}</p>'
        f'<table style="font-size: 13px; border-collapse: collapse;">'
        f'{_info_row("Apertura", f"{opened_at_label} ({elapsed_text})")}'
        f'{_info_row("Abierta por", opened_by)}'
        f'{_info_row("Reactivo inicial", f"${opening_amount}")}'
        f'</table>'
        f'{note}'
        f'</div>'
    )
    return title, html


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
