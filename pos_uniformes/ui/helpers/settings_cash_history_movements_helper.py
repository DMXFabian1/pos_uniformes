"""Helpers visibles para movimientos del corte seleccionado en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsCashMovementRowView:
    values: tuple[object, ...]
    type_tone: str


@dataclass(frozen=True)
class SettingsCashHistoryMovementsView:
    status_label: str
    rows: tuple[SettingsCashMovementRowView, ...]


def build_settings_cash_history_movements_view(
    *,
    cash_session_id: int | None,
    movements: list[dict[str, object]],
) -> SettingsCashHistoryMovementsView:
    rows = tuple(
        SettingsCashMovementRowView(
            values=(
                movement["fecha"],
                movement["tipo"],
                f"${movement['monto']}",
                movement["usuario"],
                movement["concepto"] or "-",
            ),
            type_tone=_movement_type_tone(str(movement["tipo"])),
        )
        for movement in movements
    )
    if cash_session_id is None:
        status_label = "Selecciona un corte para ver sus movimientos."
    elif movements:
        status_label = f"Movimientos registrados en la sesion #{cash_session_id}: {len(movements)}"
    else:
        status_label = f"La sesion #{cash_session_id} no tiene movimientos manuales registrados."
    return SettingsCashHistoryMovementsView(
        status_label=status_label,
        rows=rows,
    )


def _movement_type_tone(movement_type: str) -> str:
    return {
        "REACTIVO": "positive",
        "INGRESO": "warning",
        "RETIRO": "danger",
    }.get(movement_type, "muted")
