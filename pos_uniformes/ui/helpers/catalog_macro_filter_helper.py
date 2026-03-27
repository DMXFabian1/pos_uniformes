"""Helpers visibles e interactivos para chips de macro uniforme en catalogo."""

from __future__ import annotations

from collections.abc import Iterable
import unicodedata


def _normalize_macro_value(value: object) -> str:
    text = str(value or "").strip().casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def resolve_catalog_uniform_macro_selection(
    *,
    current_selection: set[str],
    macro_type: str,
) -> list[str]:
    normalized_selection = {
        _normalize_macro_value(value)
        for value in current_selection
        if str(value).strip()
    }
    if normalized_selection == {_normalize_macro_value(macro_type)}:
        return []
    return [macro_type]


def build_catalog_uniform_macro_button_states(
    *,
    available_macros: Iterable[str],
    selected_types: set[str],
) -> dict[str, bool]:
    active_macro = (
        _normalize_macro_value(next(iter(selected_types)))
        if len(selected_types) == 1
        else ""
    )
    return {
        macro_type: _normalize_macro_value(macro_type) == active_macro
        for macro_type in available_macros
    }
