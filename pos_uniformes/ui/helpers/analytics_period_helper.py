"""Helpers puros para periodo y estado visible de Analytics."""

from __future__ import annotations

from datetime import date, timedelta

from pos_uniformes.utils.date_format import local_day_window


ANALYTICS_QUICK_PERIODS: tuple[tuple[str, str], ...] = (
    ("Hoy", "today"),
    ("7 dias", "7d"),
    ("30 dias", "30d"),
    ("Mes actual", "month"),
)


def is_manual_analytics_period(period_key: object) -> bool:
    return str(period_key or "") == "manual"


def resolve_analytics_period_bounds(
    period_key: object,
    *,
    today: date,
    manual_from: date | None = None,
    manual_to: date | None = None,
) -> tuple[datetime, datetime]:
    resolved_key = str(period_key or "today")
    start_date = today
    end_date = today
    if resolved_key == "today":
        start_date = today
        end_date = today
    elif resolved_key == "7d":
        start_date = today - timedelta(days=6)
        end_date = today
    elif resolved_key == "30d":
        start_date = today - timedelta(days=29)
        end_date = today
    elif resolved_key == "month":
        start_date = today.replace(day=1)
        end_date = today
    elif resolved_key == "manual":
        start_date = manual_from or today
        end_date = manual_to or today
    if end_date < start_date:
        start_date, end_date = end_date, start_date
    start, _ = local_day_window(start_date)
    _, end = local_day_window(end_date)
    return start, end


def build_analytics_export_status_text(*, selected_client_id: object, selected_client_label: str) -> str:
    client_label = "todos" if selected_client_id in {None, ""} else selected_client_label
    return f"Periodo listo para analisis. Cliente: {client_label}."


def resolve_previous_analytics_period_bounds(
    *,
    period_start: datetime,
    period_end: datetime,
) -> tuple[datetime, datetime]:
    span = period_end - period_start
    previous_end = period_start
    previous_start = previous_end - span
    return previous_start, previous_end
