"""Helpers visibles para el historial de marketing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketingHistoryRowView:
    values: tuple[object, ...]


@dataclass(frozen=True)
class MarketingHistoryView:
    status_label: str
    rows: tuple[MarketingHistoryRowView, ...]


def build_marketing_history_view(changes: list[dict[str, object]]) -> MarketingHistoryView:
    return MarketingHistoryView(
        status_label=(
            f"Cambios registrados: {len(changes)}"
            if changes
            else "Aun no hay cambios auditados en Marketing y promociones."
        ),
        rows=tuple(
            MarketingHistoryRowView(
                values=(
                    change["created_at_label"],
                    change["username"],
                    change["role_label"],
                    change["section_label"],
                    change["field_label"],
                    change["old_value"],
                    change["new_value"],
                )
            )
            for change in changes
        ),
    )
