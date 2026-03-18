"""Helpers visibles para el listado principal de historial de caja en Configuracion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsCashHistoryRowView:
    session_id: int
    values: tuple[object, ...]
    status_tone: str
    difference_tone: str | None


def build_settings_cash_history_rows(
    cash_session_snapshots: list[dict[str, object]],
) -> tuple[SettingsCashHistoryRowView, ...]:
    rows: list[SettingsCashHistoryRowView] = []
    for snapshot in cash_session_snapshots:
        is_closed = bool(snapshot["is_closed"])
        difference = str(snapshot["difference"])
        difference_tone: str | None
        if not is_closed:
            difference_tone = None
        elif difference == "0.00":
            difference_tone = "positive"
        elif difference.startswith("-"):
            difference_tone = "danger"
        else:
            difference_tone = "warning"
        rows.append(
            SettingsCashHistoryRowView(
                session_id=int(snapshot["session_id"]),
                values=(
                    snapshot["session_id"],
                    snapshot["status_label"],
                    snapshot["opened_at"],
                    snapshot["opened_by"],
                    snapshot["opening_amount"],
                    snapshot["closed_at"],
                    snapshot["closed_by"],
                    snapshot["expected_amount"],
                    snapshot["declared_amount"],
                    snapshot["difference_amount"],
                ),
                status_tone="muted" if is_closed else "positive",
                difference_tone=difference_tone,
            )
        )
    return tuple(rows)
