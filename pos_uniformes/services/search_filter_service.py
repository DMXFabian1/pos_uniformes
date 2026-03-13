"""Helpers puros para filtros de texto en tablas."""

from __future__ import annotations

import shlex
import unicodedata


def _normalize_search_fragment(value: object) -> str:
    text = str(value or "").strip().casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize_search_text(search_text: str) -> list[str]:
    normalized = search_text.strip()
    if not normalized:
        return []
    try:
        return [_normalize_search_fragment(term) for term in shlex.split(normalized) if term.strip()]
    except ValueError:
        return [_normalize_search_fragment(term) for term in normalized.split() if term.strip()]


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

    general_haystack = " ".join(_normalize_search_fragment(row.get(field, "")) for field in general_fields)

    for term in terms:
        if ":" not in term:
            if term not in general_haystack:
                return False
            continue

        alias, raw_value = term.split(":", 1)
        fields = alias_map.get(alias.strip())
        value = raw_value.strip().strip("\"'")
        if not fields or not value:
            if term not in general_haystack:
                return False
            continue
        if not any(value in _normalize_search_fragment(row.get(field, "")) for field in fields):
            return False
    return True
