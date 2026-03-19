from __future__ import annotations

import unittest

from pos_uniformes.services.search_suggestion_service import (
    build_catalog_search_suggestions,
    build_inventory_search_suggestions,
)


class SearchSuggestionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            {
                "sku": "SKU-001",
                "producto_nombre": "Pants Deportivo",
                "producto_nombre_base": "Pants",
                "marca_nombre": "Atlas",
                "escuela_nombre": "Colegio Mexico",
                "color": "Azul Marino",
                "talla": "14",
            },
            {
                "sku": "SKU-002",
                "producto_nombre": "Corbatín Escolar",
                "producto_nombre_base": "Corbatín",
                "marca_nombre": "Atlas",
                "escuela_nombre": "Colegio Mexico",
                "color": "Rojo",
                "talla": "16",
            },
        ]

    def test_build_catalog_search_suggestions_prioritizes_plain_matches_for_normal_text(self) -> None:
        suggestions = build_catalog_search_suggestions(self.rows, search_text="az")

        self.assertEqual(suggestions[0], "Azul Marino")
        self.assertIn("color:Azul Marino", suggestions)
        self.assertGreater(suggestions.index("color:Azul Marino"), suggestions.index("Azul Marino"))

    def test_build_catalog_search_suggestions_handles_alias_prefix_query(self) -> None:
        suggestions = build_catalog_search_suggestions(self.rows, search_text="sku:")

        self.assertGreaterEqual(len(suggestions), 2)
        self.assertEqual(suggestions[0], "sku:SKU-001")
        self.assertIn("sku:SKU-002", suggestions)

    def test_build_inventory_search_suggestions_is_accent_insensitive(self) -> None:
        suggestions = build_inventory_search_suggestions(self.rows, search_text="corbatin")

        self.assertEqual(suggestions[0], "Corbatín")
        self.assertIn("producto:Corbatín", suggestions)
        self.assertGreater(suggestions.index("producto:Corbatín"), suggestions.index("Corbatín"))

    def test_build_inventory_search_suggestions_returns_empty_when_query_is_blank(self) -> None:
        self.assertEqual(build_inventory_search_suggestions(self.rows, search_text="   "), [])


if __name__ == "__main__":
    unittest.main()
