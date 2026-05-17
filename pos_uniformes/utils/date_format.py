"""Formato visible y consistente para fechas del POS."""

from __future__ import annotations

from datetime import date, datetime, time, timezone


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


def local_day_window(day: date) -> tuple[datetime, datetime]:
    """Devuelve (inicio, fin) como datetimes tz-aware en hora local para la fecha dada.

    Usar para construir ventanas de consulta a la BD en vez de UTC midnight,
    de modo que 'Hoy' cubra 00:00–23:59 hora local, no UTC.
    """
    local_tz = datetime.now(timezone.utc).astimezone().tzinfo
    return (
        datetime.combine(day, time.min, tzinfo=local_tz),
        datetime.combine(day, time.max, tzinfo=local_tz),
    )
