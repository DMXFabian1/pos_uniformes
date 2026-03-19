"""Helpers puros para periodo y estado visible de Analytics."""

from __future__ import annotations

from datetime import date, datetime, timedelta


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
    return (
        datetime.combine(start_date, datetime.min.time()),
        datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
    )


def build_analytics_export_status_text(*, selected_client_id: object, selected_client_label: str) -> str:
    client_label = "todos" if selected_client_id in {None, ""} else selected_client_label
    return f"Periodo listo para analisis. Cliente: {client_label}."
