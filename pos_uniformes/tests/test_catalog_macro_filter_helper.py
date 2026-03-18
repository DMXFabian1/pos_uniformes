from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.catalog_macro_filter_helper import (
    build_catalog_uniform_macro_button_states,
    resolve_catalog_uniform_macro_selection,
)


class CatalogMacroFilterHelperTests(unittest.TestCase):
    def test_clears_selection_when_same_macro_is_clicked(self) -> None:
        selection = resolve_catalog_uniform_macro_selection(
            current_selection={"Deportivo"},
            macro_type="Deportivo",
        )

        self.assertEqual(selection, [])

    def test_replaces_selection_when_other_macro_is_clicked(self) -> None:
        selection = resolve_catalog_uniform_macro_selection(
            current_selection={"Oficial"},
            macro_type="Escolta",
        )

        self.assertEqual(selection, ["Escolta"])

    def test_marks_only_single_active_macro(self) -> None:
        states = build_catalog_uniform_macro_button_states(
            available_macros=["Deportivo", "Oficial", "Escolta"],
            selected_types={"Oficial"},
        )

        self.assertEqual(
            states,
            {
                "Deportivo": False,
                "Oficial": True,
                "Escolta": False,
            },
        )

    def test_marks_no_macro_when_selection_is_multiple(self) -> None:
        states = build_catalog_uniform_macro_button_states(
            available_macros=["Deportivo", "Oficial"],
            selected_types={"Deportivo", "Oficial"},
        )

        self.assertEqual(
            states,
            {
                "Deportivo": False,
                "Oficial": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
