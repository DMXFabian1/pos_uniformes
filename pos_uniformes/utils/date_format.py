"""Formato visible y consistente para fechas del POS."""

from __future__ import annotations

from datetime import date, datetime


def format_display_date(value: date | datetime | None, *, empty: str = "") -> str:
    if value is None:
        return empty
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone()
        value = value.date()
    return value.strftime("%d/%m/%Y")


def format_display_datetime(value: datetime | None, *, empty: str = "") -> str:
    if value is None:
        return empty
    if value.tzinfo is not None:
        value = value.astimezone()
    return value.strftime("%d/%m/%Y %H:%M")
