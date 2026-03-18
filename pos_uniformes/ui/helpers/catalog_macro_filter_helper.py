"""Helpers visibles e interactivos para chips de macro uniforme en catalogo."""

from __future__ import annotations

from collections.abc import Iterable


def resolve_catalog_uniform_macro_selection(
    *,
    current_selection: set[str],
    macro_type: str,
) -> list[str]:
    if current_selection == {macro_type}:
        return []
    return [macro_type]


def build_catalog_uniform_macro_button_states(
    *,
    available_macros: Iterable[str],
    selected_types: set[str],
) -> dict[str, bool]:
    active_macro = next(iter(selected_types)) if len(selected_types) == 1 else ""
    return {
        macro_type: macro_type == active_macro
        for macro_type in available_macros
    }
