"""Permisos y mensajes operativos para Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteFeedbackView:
    title: str
    message: str


def build_quote_guard_feedback(action_key: str, *, can_operate: bool = True, has_selection: bool = True, has_items: bool = True) -> QuoteFeedbackView | None:
    if action_key == "create_client" and not can_operate:
        return QuoteFeedbackView("Sin permisos", "Tu usuario no puede crear clientes desde Presupuestos.")
    if action_key in {"add_item", "save_quote"} and not can_operate:
        return QuoteFeedbackView("Sin permisos", "Tu usuario no puede crear presupuestos.")
    if action_key == "remove_item" and not has_selection:
        return QuoteFeedbackView("Sin seleccion", "Selecciona una linea del presupuesto.")
    if action_key == "save_quote" and not has_items:
        return QuoteFeedbackView("Presupuesto vacio", "Agrega al menos una linea al presupuesto.")
    if action_key == "cancel_quote" and not has_selection:
        return QuoteFeedbackView("Sin seleccion", "Selecciona un presupuesto para cancelarlo.")
    return None


def build_quote_result_feedback(action_key: str, *, item_label: str = "") -> QuoteFeedbackView:
    if action_key == "save_quote":
        return QuoteFeedbackView("Presupuesto guardado", f"Presupuesto {item_label} registrado correctamente.")
    if action_key == "cancel_quote":
        return QuoteFeedbackView("Presupuesto cancelado", "El presupuesto se marco como cancelado.")
    raise ValueError(f"Accion no soportada: {action_key}")
