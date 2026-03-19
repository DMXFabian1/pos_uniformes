"""Presentacion visible de apartados en Analytics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AnalyticsLayawayLabelView:
    text: str
    tone: str


@dataclass(frozen=True)
class AnalyticsLayawayLabelsView:
    active: AnalyticsLayawayLabelView
    balance: AnalyticsLayawayLabelView
    overdue: AnalyticsLayawayLabelView
    delivered: AnalyticsLayawayLabelView


def build_analytics_layaway_labels_view(
    *,
    active_count: int,
    pending_balance: Decimal,
    overdue_count: int,
    delivered_in_period: int,
) -> AnalyticsLayawayLabelsView:
    return AnalyticsLayawayLabelsView(
        active=AnalyticsLayawayLabelView(
            text=f"Apartados activos\n{active_count}",
            tone="positive" if active_count else "neutral",
        ),
        balance=AnalyticsLayawayLabelView(
            text=f"Saldo pendiente\n${pending_balance}",
            tone="warning" if Decimal(pending_balance) > Decimal("0.00") else "neutral",
        ),
        overdue=AnalyticsLayawayLabelView(
            text=f"Vencidos\n{overdue_count}",
            tone="danger" if overdue_count else "neutral",
        ),
        delivered=AnalyticsLayawayLabelView(
            text=f"Entregados periodo\n{delivered_in_period}",
            tone="positive" if delivered_in_period else "neutral",
        ),
    )
