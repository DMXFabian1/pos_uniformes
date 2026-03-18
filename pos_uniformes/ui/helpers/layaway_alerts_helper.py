"""Helpers visibles para alertas de Apartados."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayawayAlertsView:
    alerts_rich_text: str
    quick_alerts_text: str


def build_layaway_alerts_view(
    *,
    overdue_count: int,
    due_today_count: int,
    due_week_count: int,
) -> LayawayAlertsView:
    return LayawayAlertsView(
        alerts_rich_text="".join(
            [
                _inline_metric_badge("Vencidos", overdue_count, "danger" if overdue_count else "neutral"),
                _inline_metric_badge("Hoy", due_today_count, "warning" if due_today_count else "neutral"),
                _inline_metric_badge("7 dias", due_week_count, "positive" if due_week_count else "neutral"),
            ]
        ),
        quick_alerts_text=" | ".join(
            [
                f"Apartados vencidos: {overdue_count}",
                f"Vencen hoy: {due_today_count}",
                f"Proximos 7 dias: {due_week_count}",
            ]
        ),
    )


def _inline_metric_badge(label: str, value: object, tone: str) -> str:
    palette = {
        "positive": ("#f8dfcf", "#8f4527", "#dfb496"),
        "warning": ("#fbf0cf", "#8a5a00", "#e7d49b"),
        "danger": ("#f8dfd9", "#9a2f22", "#dfb3aa"),
        "neutral": ("#fbf3ec", "#8c6656", "#ecd5c5"),
    }
    background, foreground, border = palette.get(tone, palette["neutral"])
    return (
        f"<span style=\"display:inline-block; margin-right:8px; margin-bottom:4px; "
        f"padding:5px 9px; border-radius:999px; background:{background}; color:{foreground}; "
        f"border:1px solid {border}; font-weight:700;\">"
        f"{label}: {value}</span>"
    )
