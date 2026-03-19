"""Sugerencias incrementales para busquedas de catalogo e inventario."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Sequence

SearchRow = dict[str, object]
FieldSpec = tuple[str, str]

_DEFAULT_LIMIT = 12
_CATALOG_FIELD_SPECS: tuple[FieldSpec, ...] = (
    ("sku", "sku"),
    ("producto", "producto_nombre_base"),
    ("producto", "producto_nombre"),
    ("marca", "marca_nombre"),
    ("escuela", "escuela_nombre"),
    ("color", "color"),
    ("talla", "talla"),
)
_INVENTORY_FIELD_SPECS: tuple[FieldSpec, ...] = _CATALOG_FIELD_SPECS


def _normalize_suggestion_fragment(value: object) -> str:
    text = str(value or "").strip().casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _current_query_fragment(search_text: str) -> str:
    return str(search_text or "").strip().rsplit(maxsplit=1)[-1] if str(search_text or "").strip() else ""


def _build_candidate_suggestions(
    rows: Iterable[SearchRow],
    *,
    field_specs: Sequence[FieldSpec],
) -> tuple[list[str], list[str]]:
    plain_candidates: list[str] = []
    prefixed_candidates: list[str] = []
    seen_plain: set[str] = set()
    seen_prefixed: set[tuple[str, str]] = set()

    for row in rows:
        for alias, field in field_specs:
            raw_value = str(row.get(field, "") or "").strip()
            normalized_value = _normalize_suggestion_fragment(raw_value)
            if not normalized_value or normalized_value == "-":
                continue

            if normalized_value not in seen_plain:
                seen_plain.add(normalized_value)
                plain_candidates.append(raw_value)

            prefixed_key = (alias, normalized_value)
            if prefixed_key not in seen_prefixed:
                seen_prefixed.add(prefixed_key)
                prefixed_candidates.append(f"{alias}:{raw_value}")

    return plain_candidates, prefixed_candidates


def _candidate_score(normalized_candidate: str, normalized_query: str) -> int | None:
    if not normalized_query:
        return None
    if normalized_candidate.startswith(normalized_query):
        return 0
    words = normalized_candidate.replace(":", " ").replace("-", " ").split()
    if any(word.startswith(normalized_query) for word in words):
        return 1
    if normalized_query in normalized_candidate:
        return 2
    return None


def _rank_suggestions(
    candidates: Sequence[str],
    *,
    query: str,
    limit: int,
) -> list[str]:
    normalized_query = _normalize_suggestion_fragment(query)
    if not normalized_query:
        return []

    scored_candidates: list[tuple[int, int, str]] = []
    for index, candidate in enumerate(candidates):
        score = _candidate_score(_normalize_suggestion_fragment(candidate), normalized_query)
        if score is None:
            continue
        scored_candidates.append((score, index, candidate))

    scored_candidates.sort(key=lambda item: (item[0], item[1]))
    return [candidate for _, _, candidate in scored_candidates[:limit]]


def _build_search_suggestions(
    rows: Iterable[SearchRow],
    *,
    search_text: str,
    field_specs: Sequence[FieldSpec],
    limit: int = _DEFAULT_LIMIT,
) -> list[str]:
    query_fragment = _current_query_fragment(search_text)
    if not query_fragment:
        return []

    plain_candidates, prefixed_candidates = _build_candidate_suggestions(rows, field_specs=field_specs)
    ordered_candidates = (
        [*prefixed_candidates, *plain_candidates]
        if ":" in query_fragment
        else [*plain_candidates, *prefixed_candidates]
    )
    return _rank_suggestions(
        ordered_candidates,
        query=query_fragment,
        limit=limit,
    )


def build_catalog_search_suggestions(
    rows: Iterable[SearchRow],
    *,
    search_text: str,
    limit: int = _DEFAULT_LIMIT,
) -> list[str]:
    return _build_search_suggestions(
        rows,
        search_text=search_text,
        field_specs=_CATALOG_FIELD_SPECS,
        limit=limit,
    )


def build_inventory_search_suggestions(
    rows: Iterable[SearchRow],
    *,
    search_text: str,
    limit: int = _DEFAULT_LIMIT,
) -> list[str]:
    return _build_search_suggestions(
        rows,
        search_text=search_text,
        field_specs=_INVENTORY_FIELD_SPECS,
        limit=limit,
    )
