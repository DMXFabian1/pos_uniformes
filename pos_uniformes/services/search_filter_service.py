"""Helpers puros para filtros de texto en tablas."""

from __future__ import annotations

import shlex


def tokenize_search_text(search_text: str) -> list[str]:
    normalized = search_text.strip()
    if not normalized:
        return []
    try:
        return [term.strip().lower() for term in shlex.split(normalized) if term.strip()]
    except ValueError:
        return [term.strip().lower() for term in normalized.split() if term.strip()]


def row_matches_search(
    row: dict[str, object],
    *,
    search_text: str,
    alias_map: dict[str, tuple[str, ...]],
    general_fields: tuple[str, ...],
) -> bool:
    terms = tokenize_search_text(search_text)
    if not terms:
        return True

    general_haystack = " ".join(
        str(row.get(field, "") or "").lower()
        for field in general_fields
    )

    for term in terms:
        if ":" not in term:
            if term not in general_haystack:
                return False
            continue

        alias, raw_value = term.split(":", 1)
        fields = alias_map.get(alias.strip())
        value = raw_value.strip()
        if not fields or not value:
            if term not in general_haystack:
                return False
            continue
        if not any(value in str(row.get(field, "") or "").lower() for field in fields):
            return False
    return True
