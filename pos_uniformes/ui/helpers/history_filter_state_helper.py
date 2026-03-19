"""Estado puro de filtros para el tab de Historial."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable


@dataclass(frozen=True)
class HistoryDateRangeState:
    start_datetime: datetime | None
    end_datetime: datetime | None
    start_date_label: str
    end_date_label: str


@dataclass(frozen=True)
class HistoryFilterState:
    source_filter: str
    entity_filter: str
    sku_filter: str
    type_filter: str
    source_filter_text: str
    entity_filter_text: str
    type_filter_text: str
    date_range: HistoryDateRangeState


@dataclass(frozen=True)
class HistoryTypeOptionsState:
    options: tuple[tuple[str, str], ...]
    selected_type_value: str


@dataclass(frozen=True)
class HistoryFilterResetState:
    sku_text: str
    source_index: int
    entity_index: int
    type_index: int
    from_date: date
    to_date: date


def build_history_date_range_state(
    *,
    from_date: date,
    to_date: date,
    minimum_date: date,
) -> HistoryDateRangeState:
    start_datetime = None
    start_date_label = ""
    if from_date > minimum_date:
        start_datetime = datetime.combine(from_date, datetime.min.time())
        start_date_label = from_date.isoformat()

    end_datetime = None
    end_date_label = ""
    if to_date > minimum_date:
        exclusive_end = to_date + timedelta(days=1)
        end_datetime = datetime.combine(exclusive_end, datetime.min.time())
        end_date_label = to_date.isoformat()

    return HistoryDateRangeState(
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        start_date_label=start_date_label,
        end_date_label=end_date_label,
    )


def build_history_filter_state(
    *,
    source_filter: object,
    entity_filter: object,
    sku_filter: str,
    type_filter: object,
    source_filter_text: str,
    entity_filter_text: str,
    type_filter_text: str,
    from_date: date,
    to_date: date,
    minimum_date: date,
) -> HistoryFilterState:
    return HistoryFilterState(
        source_filter=str(source_filter or ""),
        entity_filter=str(entity_filter or ""),
        sku_filter=sku_filter.strip(),
        type_filter=str(type_filter or ""),
        source_filter_text=source_filter_text,
        entity_filter_text=entity_filter_text,
        type_filter_text=type_filter_text,
        date_range=build_history_date_range_state(
            from_date=from_date,
            to_date=to_date,
            minimum_date=minimum_date,
        ),
    )


def build_history_type_options_state(
    *,
    source_filter: str,
    current_type: str,
    build_options: Callable[[str], tuple[tuple[str, str], ...]],
) -> HistoryTypeOptionsState:
    options = build_options(source_filter)
    selected_type_value = current_type if any(value == current_type for _, value in options) else ""
    return HistoryTypeOptionsState(
        options=options,
        selected_type_value=selected_type_value,
    )


def build_history_today_filter_dates(today: date) -> tuple[date, date]:
    return today, today


def build_history_clear_filter_state(minimum_date: date) -> HistoryFilterResetState:
    return HistoryFilterResetState(
        sku_text="",
        source_index=0,
        entity_index=0,
        type_index=0,
        from_date=minimum_date,
        to_date=minimum_date,
    )
