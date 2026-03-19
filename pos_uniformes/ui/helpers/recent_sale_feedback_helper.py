"""Permisos y mensajes operativos para ventas recientes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecentSaleFeedbackView:
    title: str
    message: str


def build_recent_sale_permission_label(*, is_admin: bool) -> str:
    return "" if is_admin else "La cancelacion de ventas esta restringida a ADMIN."


def build_recent_sale_guard_feedback(action_key: str, *, has_selection: bool, is_admin: bool) -> RecentSaleFeedbackView | None:
    if action_key == "view_ticket":
        if has_selection:
            return None
        return RecentSaleFeedbackView(
            title="Sin seleccion",
            message="Selecciona una venta para ver su ticket.",
        )
    if action_key == "cancel_sale":
        if not has_selection:
            return RecentSaleFeedbackView(
                title="Sin seleccion",
                message="Selecciona una venta en la tabla.",
            )
        if not is_admin:
            return RecentSaleFeedbackView(
                title="Sin permisos",
                message="Solo ADMIN puede cancelar ventas.",
            )
    return None


def build_recent_sale_result_feedback(action_key: str) -> RecentSaleFeedbackView:
    if action_key == "cancel_sale":
        return RecentSaleFeedbackView(
            title="Venta cancelada",
            message="Venta cancelada correctamente.",
        )
    raise ValueError(f"Accion no soportada: {action_key}")
